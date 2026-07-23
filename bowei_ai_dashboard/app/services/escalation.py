"""任务卡问题流转核心逻辑。

封装两个核心动作：
1. escalate_card_to_issue: 负责人在确认中心把任务卡转到问题中心
2. write_back_to_card: 问题中心 Issue 解决后，把意见回写到任务卡

设计原则：
- 确认中心只管汇报审核，统筹/决策的卡片流转到问题中心
- Issue 是"问题"的归属地，统筹/教练在问题中心处理
- Issue 解决后自动回写到任务卡，负责人回确认中心最终拍板
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..domain import issue_flow as IF
from ..time_utils import utc_now

logger = logging.getLogger(__name__)

# 任务卡状态常量（与 confirmations.py 里的卡片状态保持一致）
CARD_PENDING = "pending"
CARD_TRANSFERRED_TO_COO = "transferred_to_coordinator"
CARD_PENDING_CEO = "pending_ceo_decision"
CARD_COO_GIVEN = "coordinator_given"
CARD_CEO_DECIDED = "ceo_decided"
CARD_CONFIRMED = "confirmed"
CARD_REJECTED = "rejected"

# 负责人可操作的卡片状态（允许转出到问题中心）
CARD_OWNER_ESCALATABLE: frozenset[str] = frozenset({
    "",  # 未设状态的新卡片
    CARD_PENDING,
    CARD_COO_GIVEN,   # 统筹已反馈，负责人可再次转出
    CARD_CEO_DECIDED,  # 教练已决策，负责人可再次转出
})

# source_type 标记（独立常量，不复用 submission 的 source_type）
SOURCE_AI_CONFIRMATION = "ai_confirmation"

# target 类型
EscalationTarget = Literal["ceo", "coordinator"]


def _task_reports(data: dict) -> list[dict]:
    reports = data.get("task_reports") or []
    if not isinstance(reports, list):
        raise HTTPException(400, "task_reports must be a list")
    return reports


def _get_task_card(data: dict, card_index: int) -> tuple[list[dict], dict]:
    reports = _task_reports(data)
    if card_index < 0 or card_index >= len(reports):
        raise HTTPException(404, "task card not found")
    report = reports[card_index]
    if not isinstance(report, dict):
        raise HTTPException(400, "task card is not an object")
    return reports, report


def _card_status(report: dict) -> str:
    return (report.get("confirmation_status") or "").strip()


def build_escalation_description(
    submission: models.UpdateSubmission,
    card: dict,
    card_index: int,
    note: str,
    caller_name: str,
) -> str:
    """构造转出时 Issue.description 的完整上下文。"""
    lines: list[str] = []
    lines.append("【来自 AI 确认中心】")
    lines.append(f"提交标题：{submission.title or '（无标题）'}")
    lines.append(f"提交人：{getattr(submission, 'submitter', '') or ''}")
    lines.append(f"提交时间：{submission.created_at}")
    lines.append("")
    lines.append("---- 提交人原文 ----")
    raw_text = ""
    data = _safe_json(submission.human_result_json)
    if isinstance(data, dict):
        raw_text = (data.get("raw_text") or data.get("transcript") or "").strip()
    if not raw_text and getattr(submission, "transcript", None):
        raw_text = submission.transcript.strip()
    lines.append(raw_text or "（无原文）")
    lines.append("")
    lines.append("---- AI 任务卡内容 ----")
    lines.append(f"卡片序号：第 {card_index + 1} 张")
    lines.append(f"任务标题：{card.get('title') or card.get('task_title') or '（无标题）'}")
    result_type = card.get("result_type") or card.get("type") or ""
    if result_type:
        lines.append(f"任务类型：{result_type}")
    content = card.get("content") or card.get("result_text") or ""
    if content:
        lines.append(f"任务内容：{content}")
    assignee = card.get("assignee") or ""
    if assignee:
        lines.append(f"指派：{assignee}")
    matched = card.get("matched_subtask_title") or card.get("related_subtask_title") or ""
    if matched:
        lines.append(f"关联任务：{matched}")
    lines.append("")
    lines.append("---- 负责人转交说明 ----")
    lines.append(note or "（无说明）")
    lines.append("")
    lines.append(f"转交人：{caller_name}")
    return "\n".join(lines)


def _safe_json(raw: Any) -> Any:
    if not raw:
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def escalate_card_to_issue(
    db: Session,
    submission: models.UpdateSubmission,
    card_index: int,
    target: EscalationTarget,
    note: str,
    caller_username: str,
    caller_name: str,
    project_id: int,
    decision_by_username: str = "",
) -> models.Issue:
    """在问题中心新建一条 Issue，并把任务卡标记为已转出。

    Args:
        target: "ceo" → issue_type=需决策; "coordinator" → issue_type=待协调
        note: 负责人转交说明（必填）
        decision_by_username: 指定的统筹/教练账号（可选，空则用 need_decision_by 记录角色）

    Returns:
        新建的 Issue 对象
    """
    data = _safe_json(submission.human_result_json)
    reports, card = _get_task_card(data, card_index)

    # 校验卡片状态
    current_status = _card_status(card)
    if current_status in {CARD_TRANSFERRED_TO_COO, CARD_PENDING_CEO}:
        raise HTTPException(409, "该任务卡已转出问题中心，请等待处理完毕")
    if current_status in {CARD_CONFIRMED, CARD_REJECTED}:
        raise HTTPException(409, "该任务卡已确认/退回，不能再转出")

    # 构造 Issue
    issue_type = IF.TYPE_DECISION if target == "ceo" else IF.TYPE_COORDINATE
    status = IF.STATUS_PENDING_DECISION if target == "ceo" else IF.STATUS_COORDINATING
    description = build_escalation_description(submission, card, card_index, note, caller_name)

    issue = models.Issue(
        project_id=project_id,
        issue_type=issue_type,
        description=description,
        owner=caller_username,
        priority="中",
        status=status,
        need_decision_by=decision_by_username or ("企业教练" if target == "ceo" else "统筹人"),
        source_type=SOURCE_AI_CONFIRMATION,
        source_submission_id=submission.id,
        source_card_index=card_index,
        opinion="",
        resolution="",
    )
    db.add(issue)
    db.flush()  # 拿 issue.id

    # 更新任务卡
    new_status = CARD_PENDING_CEO if target == "ceo" else CARD_TRANSFERRED_TO_COO
    card["confirmation_status"] = new_status
    card["confirmation_note"] = note
    card["confirmation_operator"] = caller_username
    card["confirmation_at"] = utc_now().isoformat()
    card["escalated_issue_id"] = issue.id

    # 转出历史
    history = card.get("escalation_history") or []
    if not isinstance(history, list):
        history = []
    history.append({
        "issue_id": issue.id,
        "target": target,
        "note": note,
        "at": utc_now().isoformat(),
        "operator": caller_username,
    })
    card["escalation_history"] = history

    # 写回 submission
    submission.human_result_json = json.dumps(data, ensure_ascii=False)
    # 提交级状态保持原样（仍在 OWNER_ACTIONABLE），卡片级状态变了
    db.flush()
    return issue


def write_back_to_card(
    db: Session,
    issue: models.Issue,
) -> models.UpdateSubmission | None:
    """Issue 解决后，把 opinion 回写到对应的任务卡。

    Returns:
        被更新的 UpdateSubmission，找不到返回 None
    """
    if not issue.source_submission_id or issue.source_card_index is None:
        return None

    submission = db.get(models.UpdateSubmission, issue.source_submission_id)
    if not submission:
        logger.warning("write_back: submission %s not found", issue.source_submission_id)
        return None

    data = _safe_json(submission.human_result_json)
    try:
        reports, card = _get_task_card(data, issue.source_card_index)
    except HTTPException:
        logger.warning("write_back: card %s not found in submission %s", issue.source_card_index, issue.source_submission_id)
        return None

    # 根据 issue_type 决定回写的卡片状态和字段
    if issue.issue_type == IF.TYPE_DECISION:
        card["confirmation_status"] = CARD_CEO_DECIDED
        card["ceo_note"] = issue.opinion or ""
        card["ceo_operator"] = issue.need_decision_by or ""
        card["ceo_decided_at"] = utc_now().isoformat()
    else:
        card["confirmation_status"] = CARD_COO_GIVEN
        card["coordinator_note"] = issue.opinion or ""
        card["coordinator_operator"] = issue.need_decision_by or ""
        card["coordinator_feedback_at"] = utc_now().isoformat()

    # 通用回写字段
    card["confirmation_at"] = utc_now().isoformat()
    # 清除 escalated_issue_id 锁定标记（但保留 escalation_history 历史）
    card.pop("escalated_issue_id", None)

    # 最终结果：与状态流转分开展示（留痕）
    if issue.resolution:
        card["final_result"] = issue.resolution
    if issue.handler_reply:
        card["handler_reply"] = issue.handler_reply

    submission.human_result_json = json.dumps(data, ensure_ascii=False)
    db.flush()
    return submission


def is_card_escalated(report: dict) -> bool:
    """判断任务卡是否已转出到问题中心（锁定中）。"""
    return _card_status(report) in {CARD_TRANSFERRED_TO_COO, CARD_PENDING_CEO}
