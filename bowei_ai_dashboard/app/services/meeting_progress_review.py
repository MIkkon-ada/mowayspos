from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models


PROGRESS_STATUSES = {
    "completed",
    "in_progress",
    "blocked",
    "not_started",
    "not_mentioned",
}


def load_approved_baseline(project_id: int, db: Session) -> dict[str, Any]:
    run = (
        db.query(models.KickoffAgentRun)
        .filter(
            models.KickoffAgentRun.project_id == project_id,
            models.KickoffAgentRun.status == "approved",
        )
        .order_by(models.KickoffAgentRun.id.desc())
        .first()
    )
    if not run or not run.approved_snapshot_json:
        raise LookupError("approved kickoff baseline not found")
    try:
        baseline = json.loads(run.approved_snapshot_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("approved kickoff baseline is invalid JSON") from exc
    if not isinstance(baseline, dict) or not isinstance(baseline.get("tasks"), list):
        raise ValueError("approved kickoff baseline has no tasks")
    return baseline


def latest_approved_baseline_run(project_id: int, db: Session) -> models.KickoffAgentRun | None:
    return (
        db.query(models.KickoffAgentRun)
        .filter(
            models.KickoffAgentRun.project_id == project_id,
            models.KickoffAgentRun.status == "approved",
        )
        .order_by(models.KickoffAgentRun.id.desc())
        .first()
    )


def parse_named_reports(transcript: str, member_names: set[str]) -> list[dict[str, str]]:
    """Parse only exact project-member prefixes from a meeting transcript."""
    reports: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    prefix = re.compile(r"^\s*([^:：\n]{1,100})\s*[:：]\s*(.*?)\s*$")

    for raw_line in transcript.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = prefix.match(line)
        if match:
            name = match.group(1).strip()
            content = match.group(2).strip()
            current = None
            if name in member_names and content:
                current = {"member_name": name, "report_text": content}
                reports.append(current)
            continue
        if current:
            current["report_text"] = f"{current['report_text']}\n{line}".strip()

    return reports


def build_progress_prompt(baseline: dict[str, Any], reports: list[dict[str, str]]) -> str:
    return f"""你是一个只做事实核验的项目进度审核助手。

启动会已批准任务基线：
{json.dumps(baseline, ensure_ascii=False)}

本次按姓名分段的汇报：
{json.dumps(reports, ensure_ascii=False)}

请只输出 JSON 数组。每条结果必须包含 member_name、baseline_subtask_id、status、
report_text、evidence_quote、suggested_task_status、reason。
status 只能是 completed、in_progress、blocked、not_started、not_mentioned。
只有汇报原文明确支持时才允许使用 completed、in_progress、blocked 或 not_started；
无法确认时使用 not_mentioned。evidence_quote 必须是汇报原文中的短语，不能改写或补充。
不要根据项目计划推断成员已经完成工作。"""


def normalize_review_candidates(
    candidates: list[dict[str, Any]],
    transcript: str,
    member_names: set[str],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        row = dict(candidate)
        member_name = str(row.get("member_name") or "").strip()
        status = str(row.get("status") or "not_mentioned").strip()
        evidence_quote = str(row.get("evidence_quote") or "").strip()
        validation: list[str] = []

        if member_name not in member_names:
            validation.append("member is not an exact project member")
        if status not in PROGRESS_STATUSES:
            validation.append("status is invalid")
            status = "not_mentioned"
        if not evidence_quote or evidence_quote not in transcript:
            validation.append("evidence_quote is missing or not found in transcript")
            status = "not_mentioned"

        if status == "not_mentioned":
            row["suggested_task_status"] = ""
        row["member_name"] = member_name
        row["status"] = status
        row["evidence_quote"] = evidence_quote
        row["validation_json"] = json.dumps(validation, ensure_ascii=False)
        normalized.append(row)
    return normalized


def next_analysis_version(meeting_id: int, db: Session) -> int:
    current = (
        db.query(func.max(models.MeetingProgressReview.analysis_version))
        .filter(models.MeetingProgressReview.meeting_id == meeting_id)
        .scalar()
    )
    return int(current or 0) + 1
