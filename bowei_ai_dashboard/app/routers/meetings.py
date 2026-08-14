import asyncio
import hashlib
import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..ai.contracts import AIInvocationContext, Capability
from ..ai.service import AIService
from ..domain import task_status as TS
from ..database import get_db

logger = logging.getLogger("bowei.meetings")
from ..permissions import (
    PROJECT_ROLE_CEO_KEY,
    PROJECT_ROLE_COORD_KEY,
    PROJECT_ROLE_MEMBER_KEY,
    PROJECT_ROLE_OWNER_KEY,
    can_view_project,
    get_current_user_name,
    get_user_context_from_db,
    require_login,
    require_project_access,
    require_project_role,
)
from ..services.project_resolution import resolve_project_context
from ..services.project_close import require_project_business_writable
from ..services.kickoff_agent import build_kickoff_snapshot, run_kickoff_agent
from ..services.kickoff_writeback import confirm_kickoff_start
from ..services.meeting_change_set import (
    build_meeting_plan_snapshot,
    edit_meeting_change_proposal,
    execute_meeting_change_set,
    validate_meeting_change_proposal,
)
from ..services.project_meeting_minutes import (
    build_project_meeting_snapshot,
    validate_execution_schedule_proposal as validate_project_schedule_proposal,
)
from ..services.project_meeting_agent_processing import (
    process_project_meeting_agent_run,
    project_meeting_run_status_payload,
)
from ..services.meeting_document_storage import (
    MeetingDocumentStorageError,
    download_meeting_document_path,
    save_meeting_document,
)
from ..services.meeting_minutes_export import build_meeting_minutes_docx
from ..services.meeting_revisions import append_meeting_revision
from ..services.meeting_traceability import normalize_action_items
from ..services.meeting_document_text import MeetingDocumentTextError, extract_meeting_document_text
from ..services.meeting_skill_clarification import (
    BlockingClarificationsError,
    append_input_snapshot,
    resume_run,
    start_preflight,
    submit_answers,
)
from ..services.meeting_progress_review import (
    PROGRESS_STATUSES,
    build_progress_prompt,
    latest_approved_baseline_run,
    load_approved_baseline,
    next_analysis_version,
    normalize_review_candidates,
    parse_named_reports,
)
from ..time_utils import utc_now

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


def _skill_run_payload(run: models.MeetingSkillRun, db: Session) -> dict:
    """Expose the current snapshot only; historical snapshots remain auditable server-side."""
    snapshot = db.get(models.MeetingSkillInputSnapshot, run.current_input_snapshot_id)
    questions = (
        db.query(models.MeetingSkillClarification)
        .filter(
            models.MeetingSkillClarification.run_id == run.id,
            models.MeetingSkillClarification.input_snapshot_id == run.current_input_snapshot_id,
        )
        .order_by(models.MeetingSkillClarification.id.asc())
        .all()
    )
    return {
        "id": run.id,
        "project_id": run.project_id,
        "skill_name": run.skill_name,
        "skill_version": run.skill_version,
        "status": run.status,
        "current_input_snapshot_id": run.current_input_snapshot_id,
        "current_input_snapshot_version": snapshot.version if snapshot else None,
        "questions": [
            {
                "id": item.id,
                "code": item.code,
                "question": item.question,
                "question_kind": item.question_kind,
                "blocking": item.blocking,
                "required": item.required,
                "action": item.action,
                "answer_mode": item.answer_mode,
                "allow_other": item.allow_other,
                "allow_omit": item.allow_omit,
                "options": json.loads(item.options_json or "[]"),
                "evidence": json.loads(item.evidence_json or "[]"),
                "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
            }
            for item in questions
        ],
        "output": json.loads(run.output_json or "{}"),
    }


def _current_person_id(current_user: str, db: Session) -> int | None:
    account = db.query(models.Account).filter(models.Account.username == current_user).first()
    return account.person_id if account else None


def _get_accessible_skill_run(run_id: int, current_user: str, db: Session) -> models.MeetingSkillRun:
    run = db.get(models.MeetingSkillRun, run_id)
    if run is None:
        raise HTTPException(404, "Skill Run 不存在")
    require_project_access(current_user, run.project_id, db)
    return run


def _require_skill_run_ready(skill_run_id: int | None, project_id: int, db: Session) -> None:
    """Server-side gate: a skill-derived draft cannot bypass blocking questions."""
    if skill_run_id is None:
        return
    run = db.get(models.MeetingSkillRun, skill_run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(422, "Skill Run 与当前项目不匹配")
    if run.status != "ready_for_review":
        raise HTTPException(409, "存在未完成的预检或澄清项，暂不能生成或保存会议纪要")


def _kickoff_run_payload(run: models.KickoffAgentRun, db: Session) -> dict:
    payload = crud.to_dict(run)
    payload["proposals"] = [
        crud.to_dict(item)
        for item in db.query(models.KickoffChangeProposal)
        .filter_by(run_id=run.id)
        .order_by(models.KickoffChangeProposal.id.asc())
        .all()
    ]
    return payload


@router.get("/kickoff-runs")
def list_kickoff_runs(
    project_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    require_project_access(current_user, project_id, db)
    return [
        _kickoff_run_payload(run, db)
        for run in db.query(models.KickoffAgentRun)
        .filter_by(project_id=project_id)
        .order_by(models.KickoffAgentRun.id.desc())
        .all()
    ]


@router.post("/kickoff-runs")
def create_kickoff_run(
    project_id: int,
    payload: schemas.KickoffRunCreatePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    require_project_role(current_user, project_id, [PROJECT_ROLE_OWNER_KEY], db)
    project = db.get(models.Project, project_id)
    if not project or project.status != "pending_kickoff":
        raise HTTPException(409, "项目不处于待启动会状态")
    account = db.query(models.Account).filter_by(username=current_user).first()
    snapshot = build_kickoff_snapshot(project_id, db)
    try:
        package = run_kickoff_agent(
            payload.transcript_text,
            snapshot,
            lambda prompt: _do_analyze(db, payload.transcript_text, prompt),
        )
    except Exception as exc:
        logger.exception("kickoff Agent execution failed")
        raise HTTPException(502, f"启动会 Agent 运行失败: {exc}") from exc
    run = models.KickoffAgentRun(project_id=project_id, snapshot_json=json.dumps(snapshot, ensure_ascii=False), result_json=json.dumps(package, ensure_ascii=False), status="draft", created_by_person_id=account.person_id if account else None)
    db.add(run)
    db.flush()
    for proposal in package["proposals"]:
        db.add(models.KickoffChangeProposal(
            run_id=run.id,
            proposal_type=proposal["proposal_type"],
            target_type=proposal.get("target_type", ""),
            target_id=proposal.get("target_id"),
            before_json=json.dumps(proposal.get("before", {}), ensure_ascii=False),
            proposed_json=json.dumps(proposal.get("proposed", {}), ensure_ascii=False),
            evidence_json=json.dumps(proposal.get("evidence", []), ensure_ascii=False),
            validation_json=json.dumps(proposal.get("validation_errors", []), ensure_ascii=False),
        ))
    db.commit()
    db.refresh(run)
    return _kickoff_run_payload(run, db)


@router.post("/kickoff-runs/{run_id}/submit")
def submit_kickoff_run(
    run_id: int,
    payload: schemas.KickoffRunSubmitPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    run = db.get(models.KickoffAgentRun, run_id)
    if not run:
        raise HTTPException(404, "启动会审核包不存在")
    require_project_role(current_user, run.project_id, [PROJECT_ROLE_OWNER_KEY], db)
    if run.status != "draft":
        raise HTTPException(409, "启动会审核包不能重复提交")
    package = json.loads(run.result_json or "{}")
    package["summary"] = payload.summary.strip() or package.get("summary", "")
    run.result_json = json.dumps(package, ensure_ascii=False)
    run.status = "submitted"
    db.commit()
    db.refresh(run)
    return _kickoff_run_payload(run, db)


@router.post("/kickoff-runs/{run_id}/confirm-start")
def confirm_kickoff_run(
    run_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    run = db.get(models.KickoffAgentRun, run_id)
    if not run:
        raise HTTPException(404, "启动会审核包不存在")
    require_project_role(current_user, run.project_id, [PROJECT_ROLE_CEO_KEY], db)
    context = get_user_context_from_db(current_user, db)
    project, meeting = confirm_kickoff_start(run_id, context.get("name") or current_user, db)
    db.commit()
    return {"project": crud.to_dict(project), "meeting": crud.to_dict(meeting)}


@router.patch("/kickoff-runs/{run_id}/proposals/{proposal_id}/review")
def review_kickoff_proposal(
    run_id: int,
    proposal_id: int,
    payload: schemas.KickoffProposalReviewPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    run = db.get(models.KickoffAgentRun, run_id)
    proposal = db.get(models.KickoffChangeProposal, proposal_id)
    if not run or not proposal or proposal.run_id != run.id:
        raise HTTPException(404, "启动会提案不存在")
    require_project_role(current_user, run.project_id, [PROJECT_ROLE_CEO_KEY], db)
    account = db.query(models.Account).filter_by(username=current_user).first()
    if account and account.person_id and run.created_by_person_id == account.person_id:
        raise HTTPException(403, "PM 不能审核自己提交的启动会")
    if payload.status not in {"approved", "returned"}:
        raise HTTPException(422, "审核状态必须为 approved 或 returned")
    proposal.review_status = payload.status
    proposal.review_comment = payload.review_comment.strip()
    proposal.reviewer_person_id = account.person_id if account else None
    db.commit()
    db.refresh(proposal)
    return crud.to_dict(proposal)

# ── 5C 写权限检查 ─────────────────────────────────────────────
def _require_global_read_scope(context: dict) -> None:
    if not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")


def _meeting_project_id_or_raise(row: models.Meeting, context: dict, db: Session) -> int | None:
    project_id = resolve_project_context(
        db,
        project_id=row.project_id,
        related_special_project=row.related_special_project or "",
    )["project_id"]
    if project_id is not None:
        return project_id
    if context.get("is_tech_admin"):
        return None
    raise HTTPException(403, "permission denied")


def _is_meeting_creator(current_user: str, context: dict, row: models.Meeting) -> bool:
    row_host = (row.host or "").strip()
    if not row_host:
        return False
    candidates = {current_user.strip()}
    name = (context.get("name") or "").strip()
    if name:
        candidates.add(name)
    return row_host in candidates


def _can_view_meeting_draft(row: models.Meeting, current_user: str, context: dict, db: Session) -> bool:
    if context.get("is_tech_admin") or context.get("is_ceo"):
        return True
    account = db.query(models.Account).filter(models.Account.username == current_user).first()
    if account and account.person_id and row.creator_person_id == account.person_id:
        return True
    return bool(row.project_id and db.query(models.ProjectMember).filter(
        models.ProjectMember.project_id == row.project_id,
        models.ProjectMember.person_id == (account.person_id if account else None),
        models.ProjectMember.role == PROJECT_ROLE_OWNER_KEY,
    ).first())


def _row_project_id(row: models.Meeting, db: Session) -> int | None:
    return resolve_project_context(
        db,
        project_id=row.project_id,
        related_special_project=row.related_special_project or "",
    )["project_id"]


@router.get("")
def list_meetings(
    project_id: int | None = None,
    related_special_project: str | None = None,
    meeting_type: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)

    resolution = resolve_project_context(
        db,
        project_id=project_id,
        related_special_project=related_special_project,
    )
    effective_project_id: int | None = resolution["project_id"]
    if project_id is not None and not resolution["is_valid"]:
        raise HTTPException(404, "project not found")
    if project_id is None and related_special_project and effective_project_id is None:
        return []

    if effective_project_id is not None:
        require_project_access(current_user, effective_project_id, db)
    elif not related_special_project:
        _require_global_read_scope(context)

    q = db.query(models.Meeting)
    if effective_project_id is not None:
        q = q.filter(models.Meeting.project_id == effective_project_id)
    if meeting_type:
        q = q.filter(models.Meeting.meeting_type == meeting_type)

    rows = [
        crud.to_dict(r)
        for r in q.order_by(
            models.Meeting.meeting_date.desc(),
            models.Meeting.updated_at.desc(),
        ).all()
    ]
    return [r for r in rows if r.get("publish_status") == "published" or _can_view_meeting_draft(db.get(models.Meeting, r["id"]), current_user, context, db)]


@router.post("")
def create_meeting(
    payload: schemas.MeetingPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    if payload.project_id is None:
        raise HTTPException(422, "project_id is required")

    require_project_role(
        current_user,
        payload.project_id,
        [
            PROJECT_ROLE_OWNER_KEY,
            PROJECT_ROLE_COORD_KEY,
            PROJECT_ROLE_MEMBER_KEY,
        ],
        db,
    )
    require_project_business_writable(payload.project_id, db)
    _require_skill_run_ready(payload.skill_run_id, payload.project_id, db)
    project = db.get(models.Project, payload.project_id)
    if project and project.status == "pending_kickoff":
        raise HTTPException(409, "项目待启动会确认，不能创建普通会议")

    account = db.query(models.Account).filter(models.Account.username == current_user).first()
    change_set = None
    if payload.analysis_id is not None:
        change_set = db.get(models.MeetingChangeSet, payload.analysis_id)
        if not (
            change_set
            and change_set.project_id == payload.project_id
            and change_set.meeting_id is None
            and change_set.status == "draft"
            and account
            and change_set.created_by_person_id == account.person_id
        ):
            raise HTTPException(409, "meeting analysis draft cannot be attached")

    project_name = resolve_project_context(
        db,
        project_id=payload.project_id,
        related_special_project=payload.related_special_project,
    )["project_name"] or ""
    data = {
        k: v
        for k, v in payload.model_dump().items()
        if k not in {"project_id", "analysis_id", "related_special_project", "skill_run_id"}
    }
    row = models.Meeting(**data)
    row.project_id = payload.project_id
    row.creator_person_id = account.person_id if account else None
    if payload.related_special_project:
        row.related_special_project = payload.related_special_project
    elif project_name:
        row.related_special_project = project_name
    db.add(row)
    db.flush()
    if change_set is not None:
        claimed_count = (
            db.query(models.MeetingChangeSet)
            .filter(
                models.MeetingChangeSet.id == change_set.id,
                models.MeetingChangeSet.project_id == payload.project_id,
                models.MeetingChangeSet.created_by_person_id == account.person_id,
                models.MeetingChangeSet.meeting_id.is_(None),
                models.MeetingChangeSet.status == "draft",
            )
            .update(
                {
                    models.MeetingChangeSet.meeting_id: row.id,
                    models.MeetingChangeSet.status: "attached",
                },
                synchronize_session=False,
            )
        )
        if claimed_count != 1:
            raise HTTPException(409, "meeting analysis draft was attached concurrently")
        change_set.meeting_id = row.id
        change_set.status = "attached"
        crud.log(
            db,
            current_user,
            "meeting_change_set_attach",
            "meeting_change_set",
            change_set.id,
            {"meeting_id": None, "status": "draft"},
            {"meeting_id": row.id, "status": "attached"},
            project_id=row.project_id,
        )
    append_meeting_revision(db, row, saved_by=current_user)
    if row.publish_status == "draft" and row.project_id:
        from ..services.notify import company_ceo_person_ids, project_strict_owner_ids, send as _notify
        for recipient_id in set(project_strict_owner_ids(row.project_id, db) + company_ceo_person_ids(db)):
            _notify(db, recipient_id=recipient_id, ntype="meeting_draft_created",
                    title=f"会议草稿待查看：{row.title or '未命名会议'}",
                    body="可查看提交原文与 AI 提取纪要。",
                    link=f"/project/{row.project_id}/meeting?meetingId={row.id}", project_id=row.project_id)
    crud.log(db, current_user, "meeting_create", "meeting", row.id, {}, crud.to_dict(row))
    db.commit()
    db.refresh(row)
    return crud.to_dict(row)


class MeetingAnalyzeRequest(BaseModel):
    text: str
    project_id: int | None = None
    skill_run_id: int | None = None
    mode: str | None = None  # "kickoff" | "progress" | None(自动)
    member_names: list[str] | None = None  # 项目成员姓名列表，用于构建成员上下文


def _json_value(value, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def _meeting_change_proposal_payload(
    row: models.MeetingChangeProposal,
    project_id: int,
) -> dict:
    validation = _json_value(row.validation_json, {"state": "blocked", "errors": []})
    target = {"project_id": project_id}
    if row.target_type == "workstream" and row.target_id is not None:
        target["workstream_id"] = row.target_id
    if row.target_type == "subtask" and row.target_id is not None:
        target["subtask_id"] = row.target_id
    if row.target_type == "execution_schedule" and row.target_id is not None:
        target["execution_schedule_id"] = row.target_id
    if row.parent_workstream_id is not None:
        target["parent_workstream_id"] = row.parent_workstream_id
    return {
        "id": row.id,
        "action": row.action,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "parent_workstream_id": row.parent_workstream_id,
        "target": target,
        "before": _json_value(row.before_json, {}),
        "proposed": _json_value(row.proposed_json, {}),
        "evidence": _json_value(row.evidence_json, []),
        "reason": row.reason,
        "confidence": row.confidence,
        "validation": validation,
        "execution_status": row.execution_status,
        "executed_by_person_id": row.executed_by_person_id,
        "executed_at": row.executed_at,
        "result_target_id": row.result_target_id,
    }


def _meeting_change_set_payload(row: models.MeetingChangeSet, db: Session) -> dict:
    proposals = (
        db.query(models.MeetingChangeProposal)
        .filter_by(change_set_id=row.id)
        .order_by(models.MeetingChangeProposal.id.asc())
        .all()
    )
    return {
        "id": row.id,
        "project_id": row.project_id,
        "status": row.status,
        "proposals": [
            _meeting_change_proposal_payload(proposal, row.project_id)
            for proposal in proposals
        ],
    }


def _proposal_target_columns(proposal: dict) -> tuple[str, int | None, int | None]:
    action = proposal.get("action")
    target = proposal.get("target") or {}
    if action == "update_workstream":
        return "workstream", target.get("workstream_id"), None
    if action == "update_subtask":
        return "subtask", target.get("subtask_id"), target.get("parent_workstream_id")
    if action == "create_subtask":
        return "subtask", None, target.get("parent_workstream_id")
    if action == "update_execution_schedule":
        return "execution_schedule", target.get("execution_schedule_id"), target.get("subtask_id")
    if action == "create_execution_schedule":
        return "execution_schedule", None, target.get("subtask_id")
    return "workstream", None, None


def _persist_meeting_change_set(
    *,
    project_id: int,
    transcript_text: str,
    raw_result: dict,
    snapshot: dict,
    current_user: str,
    db: Session,
) -> models.MeetingChangeSet:
    raw_proposals = raw_result.get("change_set") if isinstance(raw_result.get("change_set"), list) else []
    proposals = [
        validate_meeting_change_proposal(raw, snapshot, transcript_text)
        for raw in raw_proposals
    ]
    account = db.query(models.Account).filter_by(username=current_user).first()
    change_set = models.MeetingChangeSet(
        project_id=project_id,
        created_by_person_id=account.person_id if account else None,
        transcript_hash=hashlib.sha256(transcript_text.encode("utf-8")).hexdigest(),
        snapshot_json=json.dumps(snapshot, ensure_ascii=False, allow_nan=False),
        result_json=json.dumps(raw_result, ensure_ascii=False, allow_nan=False),
        status="draft",
    )
    db.add(change_set)
    db.flush()
    for proposal in proposals:
        target_type, target_id, parent_workstream_id = _proposal_target_columns(proposal)
        db.add(
            models.MeetingChangeProposal(
                change_set_id=change_set.id,
                action=proposal["action"],
                target_type=target_type,
                target_id=target_id,
                parent_workstream_id=parent_workstream_id,
                before_json=json.dumps(proposal["before"], ensure_ascii=False, allow_nan=False),
                proposed_json=json.dumps(proposal["proposed"], ensure_ascii=False, allow_nan=False),
                evidence_json=json.dumps(proposal["evidence"], ensure_ascii=False, allow_nan=False),
                reason=proposal["reason"],
                confidence=proposal["confidence"],
                validation_json=json.dumps(proposal["validation"], ensure_ascii=False, allow_nan=False),
                execution_status="pending",
            )
        )
    db.commit()
    db.refresh(change_set)
    return change_set


def _meeting_change_set_prompt(snapshot: dict) -> str:
    snapshot_text = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    return f"""

【工作推进表变更提案】
此次请求已提供项目 ID，change_set 是必填字段；没有明确、可引用的变更时必须输出空数组。会议转录文字是唯一事实来源。下面的冻结快照只用于识别现有记录的 ID 和当前字段，绝不能把快照内容当作会议事实、补全会议内容或推断变更。

冻结快照：
```json
{snapshot_text}
```

change_set 中每一项必须严格为：
{{
  "action": "create_workstream|update_workstream|create_subtask|update_subtask",
  "target": {{"project_id": {snapshot.get("project_id")}, "workstream_id": 0, "subtask_id": 0, "parent_workstream_id": 0}},
  "proposed": {{}},
  "evidence": ["会议转录中的逐字连续引文"],
  "reason": "该引文为何支持这一项变更",
  "confidence": 0.0
}}

规则：
- 只允许上述四种 action；update_workstream 必须使用快照中的 workstream_id，update_subtask 必须使用快照中的 subtask_id，create_subtask 必须使用快照中的 parent_workstream_id。
- 引文必须是会议转录中的逐字连续片段，每项至少一条；不得概括、改写或凭常识补全。
- 目标不明确时不得猜测任何 ID：保留能说明歧义的文字并省略该 ID，让系统将其标记为待复核。
- create_workstream 只能在原文明示新增重点工作时提出；create_subtask 只能在原文明示新增关键任务时提出。
- 不得删除重点工作或关键任务，不得创建问题、成果、决策或修改项目成员。
"""


@router.post("/skill-runs/preflight")
def create_meeting_skill_preflight(
    payload: schemas.MeetingSkillPreflightPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    require_project_role(
        current_user,
        payload.project_id,
        [PROJECT_ROLE_OWNER_KEY, PROJECT_ROLE_COORD_KEY, PROJECT_ROLE_MEMBER_KEY],
        db,
    )
    run = start_preflight(
        db,
        project_id=payload.project_id,
        created_by_person_id=_current_person_id(current_user, db),
        meeting_type=payload.meeting_type,
        transcript_text=payload.transcript_text,
        reference_files=[item.model_dump() for item in payload.reference_files],
    )
    return _skill_run_payload(run, db)


@router.get("/skill-runs/{run_id}")
def get_meeting_skill_run(
    run_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    return _skill_run_payload(_get_accessible_skill_run(run_id, current_user, db), db)


@router.post("/skill-runs/{run_id}/snapshots")
def add_meeting_skill_snapshot(
    run_id: int,
    payload: schemas.MeetingSkillSnapshotPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    run = _get_accessible_skill_run(run_id, current_user, db)
    run = append_input_snapshot(
        db,
        run,
        transcript_text=payload.transcript_text,
        reference_files=[item.model_dump() for item in payload.reference_files],
    )
    return _skill_run_payload(run, db)


@router.post("/skill-runs/{run_id}/answers")
def answer_meeting_skill_questions(
    run_id: int,
    payload: schemas.MeetingSkillAnswersPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    run = _get_accessible_skill_run(run_id, current_user, db)
    try:
        run = submit_answers(
            db,
            run,
            answers=[item.model_dump() for item in payload.answers],
            answered_by_person_id=_current_person_id(current_user, db),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _skill_run_payload(run, db)


@router.post("/skill-runs/{run_id}/resume")
def resume_meeting_skill_run(
    run_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    run = _get_accessible_skill_run(run_id, current_user, db)
    try:
        run = resume_run(db, run)
    except BlockingClarificationsError as exc:
        raise HTTPException(
            409,
            {"message": str(exc), "question_ids": [question.id for question in exc.questions]},
        ) from exc
    return _skill_run_payload(run, db)


@router.post("/extract-document-text")
async def extract_document_text(
    project_id: int,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    require_project_access(current_user, project_id, db)
    filename = file.filename or ""
    content = await file.read()
    try:
        text = extract_meeting_document_text(filename, content)
    except MeetingDocumentTextError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "filename": filename,
        "text": text,
        # New project meeting documents are interpreted only by the Agent.
        # Preserve the response key so older clients do not fail during rollout.
        "standard_minutes": None,
    }


def _project_meeting_document_root() -> Path:
    configured = os.getenv("PROJECT_MEETING_DOCUMENT_ROOT", "").strip()
    root = Path(configured) if configured else Path(__file__).resolve().parents[2] / "data" / "meeting_documents"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _project_meeting_payload(run: models.ProjectMeetingRun, db: Session) -> dict:
    source = db.get(models.MeetingDocumentSource, run.document_source_id)
    meeting = db.query(models.Meeting).filter(models.Meeting.document_source_id == run.document_source_id).first()
    change_set = (
        db.query(models.MeetingChangeSet).filter_by(meeting_id=meeting.id).first()
        if meeting else None
    )
    result = _json_value(run.result_json, {})
    return {
        "id": run.id,
        "project_id": run.project_id,
        "status": run.status,
        "stage": run.stage,
        "step_count": run.step_count,
        "error_code": run.error_code or "",
        "error_message": run.error_message or "",
        "document": {
            "id": source.id if source else None,
            "original_name": source.original_name if source else "",
            "mime_type": source.mime_type if source else "",
            "size_bytes": source.size_bytes if source else 0,
            "content_hash": source.content_hash if source else "",
        },
        "meeting_id": meeting.id if meeting else None,
        "meeting": crud.to_dict(meeting) if meeting else None,
        "snapshot": _json_value(run.snapshot_json, {}),
        "result": result,
        "review_package": _meeting_change_set_payload(change_set, db) if change_set else None,
    }


def _project_meeting_change_set(
    project_id: int,
    meeting_id: int,
    created_by_person_id: int | None,
    document_text: str,
    snapshot: dict,
    result: dict,
    db: Session,
) -> models.MeetingChangeSet:
    change_set = models.MeetingChangeSet(
        project_id=project_id,
        meeting_id=meeting_id,
        created_by_person_id=created_by_person_id,
        transcript_hash=hashlib.sha256(document_text.encode("utf-8")).hexdigest(),
        snapshot_json=json.dumps(snapshot, ensure_ascii=False),
        result_json=json.dumps(result, ensure_ascii=False),
        status="draft",
    )
    db.add(change_set)
    db.flush()
    for raw in result.get("execution_schedule_changes", []):
        if not isinstance(raw, dict):
            continue
        target = raw.get("target") if isinstance(raw.get("target"), dict) else {}
        action = raw.get("action") or ""
        if action not in {"update_execution_schedule", "create_execution_schedule"}:
            continue
        db.add(models.MeetingChangeProposal(
            change_set_id=change_set.id,
            action=action,
            target_type="execution_schedule",
            target_id=target.get("execution_schedule_id"),
            parent_workstream_id=target.get("key_task_id", target.get("subtask_id")),
            before_json=json.dumps(raw.get("before", {}), ensure_ascii=False),
            proposed_json=json.dumps(raw.get("proposed", {}), ensure_ascii=False),
            evidence_json=json.dumps(raw.get("evidence", []), ensure_ascii=False),
            reason=str(raw.get("reason") or ""),
            confidence=float(raw.get("confidence") or 0),
            validation_json=json.dumps(raw.get("validation", {}), ensure_ascii=False),
            execution_status="pending",
        ))
    db.flush()
    return change_set


@router.post("/document-runs")
async def create_project_meeting_document_run(
    background_tasks: BackgroundTasks,
    project_id: int = Form(...),
    meeting_type: str = Form(""),
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    if not db.get(models.Project, project_id):
        raise HTTPException(404, "project not found")
    require_project_access(current_user, project_id, db)
    content = await file.read()
    try:
        saved = save_meeting_document(_project_meeting_document_root(), project_id, file.filename or "", content)
        document_text = extract_meeting_document_text(file.filename or "", content)
    except (MeetingDocumentStorageError, MeetingDocumentTextError) as exc:
        raise HTTPException(422, str(exc)) from exc

    account = db.query(models.Account).filter_by(username=current_user).first()
    snapshot = build_project_meeting_snapshot(project_id, db)
    snapshot["requested_meeting_type"] = str(meeting_type or "").strip()
    source = models.MeetingDocumentSource(
        project_id=project_id,
        original_name=saved["original_name"],
        storage_key=saved["storage_key"],
        mime_type=saved["mime_type"],
        size_bytes=saved["size_bytes"],
        content_hash=saved["content_hash"],
        uploaded_by_person_id=account.person_id if account else None,
    )
    db.add(source)
    db.flush()
    run = models.ProjectMeetingRun(
        project_id=project_id,
        document_source_id=source.id,
        snapshot_json=json.dumps(snapshot, ensure_ascii=False),
        document_text=document_text,
        status="queued",
        stage="reading",
        created_by_person_id=account.person_id if account else None,
    )
    db.add(run)
    db.flush()

    db.commit()
    db.refresh(run)
    background_tasks.add_task(process_project_meeting_agent_run, run.id)
    return _project_meeting_payload(run, db)


@router.get("/document-runs/{run_id}")
def get_project_meeting_document_run(run_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    current_user = require_login(current_user, db)
    run = db.get(models.ProjectMeetingRun, run_id)
    if not run:
        raise HTTPException(404, "meeting document run not found")
    require_project_access(current_user, run.project_id, db)
    return _project_meeting_payload(run, db)


@router.get("/document-runs/{run_id}/status")
def get_project_meeting_document_run_status(run_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    current_user = require_login(current_user, db)
    run = db.get(models.ProjectMeetingRun, run_id)
    if not run:
        raise HTTPException(404, "meeting document run not found")
    require_project_access(current_user, run.project_id, db)
    return project_meeting_run_status_payload(run)


@router.get("/{meeting_id}/review-package")
def get_project_meeting_review_package(meeting_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    current_user = require_login(current_user, db)
    row = _meeting_for_read(meeting_id, current_user, db)
    if not row.document_source_id:
        raise HTTPException(404, "project meeting document run not found")
    source = db.get(models.MeetingDocumentSource, row.document_source_id)
    run = db.query(models.ProjectMeetingRun).filter_by(document_source_id=row.document_source_id).order_by(models.ProjectMeetingRun.id.desc()).first()
    if not source or not run:
        raise HTTPException(404, "project meeting document run not found")
    return _project_meeting_payload(run, db)


@router.get("/{meeting_id}/document-download")
def download_project_meeting_document(meeting_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    current_user = require_login(current_user, db)
    row = _meeting_for_read(meeting_id, current_user, db)
    source = db.get(models.MeetingDocumentSource, row.document_source_id) if row.document_source_id else None
    if not source:
        raise HTTPException(404, "meeting document not found")
    try:
        path = download_meeting_document_path(_project_meeting_document_root(), source.storage_key)
    except MeetingDocumentStorageError as exc:
        raise HTTPException(404, str(exc)) from exc
    return FileResponse(path, media_type=source.mime_type, filename=source.original_name)


@router.get("/{meeting_id}/document-export")
def export_project_meeting_minutes(meeting_id: int, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    current_user = require_login(current_user, db)
    meeting = _meeting_for_read(meeting_id, current_user, db)
    source = db.get(models.MeetingDocumentSource, meeting.document_source_id) if meeting.document_source_id else None
    content = build_meeting_minutes_docx(meeting, source_name=source.original_name if source else "")
    filename = f"{(meeting.title or '项目会议纪要').strip()}-会议纪要.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


def _project_meeting_snapshot_schedule(snapshot: dict, schedule_id: int) -> dict | None:
    for workstream in snapshot.get("workstreams", []):
        for key_task in workstream.get("key_tasks", []) if isinstance(workstream, dict) else []:
            for schedule in key_task.get("execution_schedules", []) if isinstance(key_task, dict) else []:
                if isinstance(schedule, dict) and schedule.get("id") == schedule_id:
                    return schedule
    return None


def _execute_project_meeting_schedule_changes(
    meeting: models.Meeting,
    proposal_ids: list[int],
    actor: str,
    db: Session,
) -> list[models.MeetingChangeProposal]:
    run = (
        db.query(models.ProjectMeetingRun)
        .filter(models.ProjectMeetingRun.document_source_id == meeting.document_source_id)
        .order_by(models.ProjectMeetingRun.id.desc())
        .first()
    )
    change_set = db.query(models.MeetingChangeSet).filter_by(meeting_id=meeting.id).first()
    if not run or not change_set:
        raise HTTPException(404, "project meeting review package not found")
    if not proposal_ids:
        return []
    proposals = (
        db.query(models.MeetingChangeProposal)
        .filter(
            models.MeetingChangeProposal.change_set_id == change_set.id,
            models.MeetingChangeProposal.id.in_(proposal_ids),
        )
        .all()
    )
    if len(proposals) != len(set(proposal_ids)):
        raise HTTPException(409, "selected proposal does not belong to meeting")
    snapshot = _json_value(run.snapshot_json, {})
    for proposal in proposals:
        if proposal.execution_status != "pending":
            raise HTTPException(409, "selected proposal is not pending")
        target = {"project_id": meeting.project_id}
        if proposal.target_id is not None:
            target["execution_schedule_id"] = proposal.target_id
        if proposal.parent_workstream_id is not None:
            target["key_task_id"] = proposal.parent_workstream_id
        raw = {
            "action": proposal.action,
            "target": target,
            "proposed": _json_value(proposal.proposed_json, {}),
            "evidence": _json_value(proposal.evidence_json, []),
            "reason": proposal.reason,
            "confidence": proposal.confidence,
        }
        validated = validate_project_schedule_proposal(raw, snapshot, run.document_text or "")
        if validated["validation"]["state"] != "ready":
            raise HTTPException(409, "selected proposal failed revalidation")
        if proposal.action == "update_execution_schedule":
            live = db.get(models.ExecutionSchedule, proposal.target_id)
            if not live or live.is_deleted:
                raise HTTPException(409, "execution schedule target is stale or deleted")
            before = validated.get("before", {})
            current = {
                field: (
                    getattr(live, field).isoformat() if field in {"start_date", "due_date"} and getattr(live, field) else getattr(live, field, None)
                )
                for field in before
            }
            if current != before:
                raise HTTPException(409, "execution schedule target changed after analysis")
    account = db.query(models.Account).filter_by(username=actor).first()
    executed: list[models.MeetingChangeProposal] = []
    from datetime import date
    for proposal in proposals:
        proposed = _json_value(proposal.proposed_json, {})
        if proposal.action == "update_execution_schedule":
            row = db.get(models.ExecutionSchedule, proposal.target_id)
            for field, value in proposed.items():
                if field in {"start_date", "due_date"} and value:
                    value = date.fromisoformat(value)
                setattr(row, field, value)
        else:
            subtask = db.get(models.SubTask, proposal.parent_workstream_id)
            if not subtask:
                raise HTTPException(409, "key task no longer exists")
            values = dict(proposed)
            for field in {"start_date", "due_date"}:
                if values.get(field):
                    values[field] = date.fromisoformat(values[field])
            row = models.ExecutionSchedule(
                subtask_id=subtask.id,
                created_by=actor,
                updated_by=actor,
                **values,
            )
            db.add(row)
            db.flush()
        proposal.result_target_id = row.id
        proposal.execution_status = "executed"
        proposal.executed_by_person_id = account.person_id if account else None
        proposal.executed_at = utc_now()
        executed.append(proposal)
    change_set.status = "executed" if executed else change_set.status
    return executed


@router.post("/{meeting_id}/review")
def review_project_meeting(
    meeting_id: int,
    payload: schemas.ProjectMeetingReviewPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    meeting = _meeting_for_read(meeting_id, current_user, db)
    if not meeting.project_id or not meeting.document_source_id:
        raise HTTPException(409, "only project document meetings support this review flow")
    require_project_role(current_user, meeting.project_id, [PROJECT_ROLE_OWNER_KEY], db)
    if meeting.review_status not in {"pending_review", "returned"}:
        raise HTTPException(409, "meeting is not awaiting owner review")
    account = db.query(models.Account).filter_by(username=current_user).first()
    if payload.action == "return":
        meeting.review_status = "returned"
        meeting.publish_status = "draft"
        db.add(models.MeetingReviewEvent(
            meeting_id=meeting.id,
            action="returned",
            actor_person_id=account.person_id if account else None,
            reason=payload.reason,
            selected_proposal_ids_json="[]",
        ))
    else:
        _execute_project_meeting_schedule_changes(meeting, payload.proposal_ids, current_user, db)
        meeting.review_status = "approved"
        meeting.publish_status = "published"
        meeting.review_version = (meeting.review_version or 0) + 1
        db.add(models.MeetingReviewEvent(
            meeting_id=meeting.id,
            action="approved",
            actor_person_id=account.person_id if account else None,
            selected_proposal_ids_json=json.dumps(payload.proposal_ids),
        ))
    db.commit()
    db.refresh(meeting)
    return crud.to_dict(meeting)


def _project_member_names(project_id: int | None, db: Session) -> set[str]:
    if not project_id:
        return set()
    rows = db.query(models.ProjectMember.person_name_snapshot).filter(
        models.ProjectMember.project_id == project_id,
    ).all()
    return {str(row[0]).strip() for row in rows if row[0] and str(row[0]).strip()}


def _tag_action_item_members(action_items: list, project_id: int | None, db: Session) -> list:
    member_names = _project_member_names(project_id, db)
    tagged: list = []
    for item in action_items:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        candidate = str(row.get("member") or "").strip()
        row["member"] = candidate if candidate in member_names else "待确认"
        row["deadline"] = str(row.get("deadline") or "待确认").strip()
        row["acceptance_criteria"] = str(row.get("acceptance_criteria") or "待确认").strip()
        row["evidence_quote"] = str(
            row.get("evidence_quote") or row.get("evidence") or "待确认"
        ).strip()
        tagged.append(row)
    return tagged


def _tag_report_members(reports: list, project_id: int | None, db: Session) -> list:
    """仅将 AI 从原文提取出的发言归属与真实项目成员精确匹配。"""
    member_names = _project_member_names(project_id, db)
    tagged: list = []
    for item in reports:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        if not str(row.get("content") or "").strip():
            continue
        candidate = str(row.get("member") or "").strip()
        row["member"] = candidate if candidate in member_names else "待确认"
        tagged.append(row)
    return tagged


@router.post("/analyze")
async def analyze_meeting(
    payload: MeetingAnalyzeRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    if payload.project_id is not None:
        if not db.get(models.Project, payload.project_id):
            raise HTTPException(404, "project not found")
        require_project_access(current_user, payload.project_id, db)
        _require_skill_run_ready(payload.skill_run_id, payload.project_id, db)
    elif payload.mode == "progress":
        raise HTTPException(422, "project_id is required for progress meeting analysis")

    if not payload.text.strip():
        raise HTTPException(422, "text 不能为空")

    # 推进表只提供关联与核对上下文；会议原文仍是唯一的纪要事实来源。
    snapshot = (
        build_meeting_plan_snapshot(payload.project_id, db)
        if payload.project_id is not None
        else None
    )
    project_member_names = sorted(_project_member_names(payload.project_id, db))
    work_plan_context = _build_all_members_context(project_member_names, payload.project_id, db)
    member_context_text = work_plan_context
    tasks_context_text = work_plan_context

    # 仅把明确的说话人标记当作“逐人汇报”。议程序号、表格编号、日期等数字
    # 都不能触发成员上下文提示词，否则会把标准会议纪要改写成成员进度报告。
    has_speakers = bool(re.search(r"(?im)^\s*(?:说话人|speaker)\s*\d*\s*[:：]", payload.text))

    # 用户明确选择了模式就用指定 prompt；否则自动检测
    if payload.mode == "progress":
        prompt = _PROMPT_REPORT.format(
            member_context=member_context_text or "（暂无成员上下文）",
            text=payload.text[:10000],
        )
    elif payload.mode == "kickoff":
        prompt = _PROMPT_GENERIC.format(
            tasks_context=tasks_context_text or "（暂无当前计划数据）",
            text=payload.text[:8000],
        )
    else:
        # 自动检测：如果转写文本里有说话人编号，就使用带成员背景的提示词
        if has_speakers:
            prompt = _PROMPT_REPORT.format(
                member_context=member_context_text or "（暂无成员上下文）",
                text=payload.text[:10000],
            )
        else:
            prompt = _PROMPT_GENERIC.format(
                tasks_context=tasks_context_text or "（暂无当前计划数据）",
                text=payload.text[:8000],
            )

    if snapshot is not None:
        prompt += _meeting_change_set_prompt(snapshot)
    prompt += """
HARD TRACEABILITY RULES:
- Only extract work items, decisions, and risks explicitly supported by the transcript.
- Every action_items entry must include member, task, deadline, acceptance_criteria, and evidence_quote.
- evidence_quote must be a short verbatim quote from the transcript; if unavailable, return 待确认.
- If member, deadline, or acceptance_criteria is not explicit, return 待确认 instead of inferring it.
- Never use project context as evidence for a meeting fact.
"""

    try:
        result = await asyncio.to_thread(_do_analyze, db, payload.text, prompt)
    except Exception as exc:
        logger.warning("meeting analyze failed: %s", exc)
        raise HTTPException(500, f"AI analysis failed: {exc}")

    reports = _tag_report_members(result.get("reports") or [], payload.project_id, db)
    confirmed_items = result.get("confirmed_items") or []
    decision_requests = result.get("decision_requests") or []
    action_items = _tag_action_item_members(
        result.get("action_items") or result.get("task_list") or [],
        payload.project_id,
        db,
    )
    action_items = normalize_action_items(action_items, payload.text)

    response = {
        "title": result.get("title", ""),
        "meeting_type": result.get("meeting_type", ""),
        "meeting_date": result.get("meeting_date", ""),
        "host": result.get("host", ""),
        "participants": "",
        "summary": result.get("summary", ""),
        "reports_json": json.dumps(reports, ensure_ascii=False),
        "task_list_json": json.dumps(action_items, ensure_ascii=False),
        "confirmed_items_json": json.dumps(confirmed_items, ensure_ascii=False),
        "decision_items_json": json.dumps(decision_requests, ensure_ascii=False),
        "risk_items_json": json.dumps(confirmed_items, ensure_ascii=False),
        "transcript_text": payload.text,
        "has_speakers": has_speakers,
    }
    if snapshot is None:
        response["analysis_id"] = None
        response["change_set"] = None
        return response

    try:
        change_set = _persist_meeting_change_set(
            project_id=payload.project_id,
            transcript_text=payload.text,
            raw_result=result,
            snapshot=snapshot,
            current_user=current_user,
            db=db,
        )
    except Exception as exc:
        db.rollback()
        logger.exception("meeting change-set analysis persistence failed")
        raise HTTPException(500, f"meeting change-set persistence failed: {exc}") from exc

    response["analysis_id"] = change_set.id
    response["change_set"] = _meeting_change_set_payload(change_set, db)
    return response


def _progress_baseline_index(baseline: dict) -> dict[int, tuple[int | None, dict, dict]]:
    index: dict[int, tuple[int | None, dict, dict]] = {}
    for task in baseline.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        for subtask in task.get("subtasks") or []:
            if not isinstance(subtask, dict) or not isinstance(subtask.get("id"), int):
                continue
            index[subtask["id"]] = (task_id, task, subtask)
    return index


def _progress_status_to_task_status(status: str) -> str | None:
    return {
        "completed": TS.S_COMPLETED,
        "in_progress": TS.S_IN_PROGRESS,
        "not_started": TS.S_NOT_STARTED,
    }.get(status)


@router.post("/{row_id}/progress-review/analyze")
async def analyze_progress_review(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    meeting = db.get(models.Meeting, row_id)
    if not meeting:
        raise HTTPException(404, "meeting not found")
    project_id = _meeting_project_id_or_raise(meeting, context, db)
    if project_id is None:
        raise HTTPException(409, "progress review requires a project")
    require_project_access(current_user, project_id, db)

    baseline_run = latest_approved_baseline_run(project_id, db)
    if not baseline_run or not baseline_run.approved_snapshot_json:
        raise HTTPException(409, "approved kickoff baseline not found")
    try:
        baseline = load_approved_baseline(project_id, db)
    except (LookupError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc

    member_names = _project_member_names(project_id, db)
    reports = parse_named_reports(meeting.transcript_text or "", member_names)
    if not reports:
        raise HTTPException(422, "transcript must contain named reports in 姓名：内容 format")

    prompt = build_progress_prompt(baseline, reports)
    try:
        result = await asyncio.to_thread(
            _do_analyze,
            db,
            meeting.transcript_text or "",
            prompt,
            resource_id=row_id,
        )
    except Exception as exc:
        logger.warning("meeting progress review failed: %s", exc)
        raise HTTPException(502, f"progress review analysis failed: {exc}") from exc

    candidates = result if isinstance(result, list) else result.get("reviews") or []
    normalized = normalize_review_candidates(candidates, meeting.transcript_text or "", member_names)
    baseline_index = _progress_baseline_index(baseline)
    analysis_version = next_analysis_version(row_id, db)

    for previous in (
        db.query(models.MeetingProgressReview)
        .filter(
            models.MeetingProgressReview.meeting_id == row_id,
            models.MeetingProgressReview.review_status == "pending",
        )
        .all()
    ):
        previous.review_status = "ignored"
        previous.review_comment = f"superseded by analysis version {analysis_version}"

    saved: list[models.MeetingProgressReview] = []
    for candidate in normalized:
        subtask_id = candidate.get("baseline_subtask_id")
        task_id, task_snapshot, subtask_snapshot = (
            baseline_index.get(subtask_id, (None, {}, {}))
            if isinstance(subtask_id, int)
            else (None, {}, {})
        )
        validation = json.loads(candidate.get("validation_json") or "[]")
        if not isinstance(subtask_id, int) or subtask_id not in baseline_index:
            validation.append("baseline_subtask_id is not in the approved kickoff baseline")
        row = models.MeetingProgressReview(
            project_id=project_id,
            meeting_id=row_id,
            baseline_run_id=baseline_run.id,
            baseline_task_id=task_id,
            baseline_subtask_id=subtask_id if isinstance(subtask_id, int) else None,
            member_name=str(candidate.get("member_name") or ""),
            baseline_snapshot_json=json.dumps(
                {"task": task_snapshot, "subtask": subtask_snapshot},
                ensure_ascii=False,
            ),
            report_text=str(candidate.get("report_text") or ""),
            status=str(candidate.get("status") or "not_mentioned"),
            evidence_quote=str(candidate.get("evidence_quote") or ""),
            suggested_task_status=str(candidate.get("suggested_task_status") or ""),
            review_status="pending",
            validation_json=json.dumps(validation, ensure_ascii=False),
            analysis_version=analysis_version,
        )
        db.add(row)
        saved.append(row)

    db.commit()
    return {
        "meeting_id": row_id,
        "analysis_version": analysis_version,
        "reviews": [crud.to_dict(row) for row in saved],
    }


@router.get("/{row_id}/progress-review")
def list_progress_reviews(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    meeting = db.get(models.Meeting, row_id)
    if not meeting:
        raise HTTPException(404, "meeting not found")
    project_id = _meeting_project_id_or_raise(meeting, context, db)
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    rows = (
        db.query(models.MeetingProgressReview)
        .filter(models.MeetingProgressReview.meeting_id == row_id)
        .order_by(
            models.MeetingProgressReview.analysis_version.desc(),
            models.MeetingProgressReview.id.asc(),
        )
        .all()
    )
    return [crud.to_dict(row) for row in rows]


@router.patch("/{row_id}/progress-review/{review_id}")
def patch_progress_review(
    row_id: int,
    review_id: int,
    payload: schemas.MeetingProgressReviewPatch,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    meeting = db.get(models.Meeting, row_id)
    review = db.get(models.MeetingProgressReview, review_id)
    if not meeting or not review or review.meeting_id != row_id:
        raise HTTPException(404, "progress review not found")
    project_id = _meeting_project_id_or_raise(meeting, context, db)
    if project_id is not None:
        require_project_role(
            current_user,
            project_id,
            [PROJECT_ROLE_OWNER_KEY, PROJECT_ROLE_COORD_KEY],
            db,
        )
    if review.review_status == "accepted":
        raise HTTPException(409, "accepted progress review cannot be edited")
    if payload.status is not None:
        review.status = payload.status
    if payload.suggested_task_status:
        review.suggested_task_status = payload.suggested_task_status.strip()
    if payload.review_status is not None:
        review.review_status = payload.review_status
    review.review_comment = payload.review_comment.strip()
    db.commit()
    db.refresh(review)
    return crud.to_dict(review)


@router.post("/{row_id}/progress-review/{review_id}/confirm")
def confirm_progress_review(
    row_id: int,
    review_id: int,
    payload: schemas.MeetingProgressReviewConfirm,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    meeting = db.get(models.Meeting, row_id)
    review = db.get(models.MeetingProgressReview, review_id)
    if not meeting or not review or review.meeting_id != row_id:
        raise HTTPException(404, "progress review not found")
    project_id = _meeting_project_id_or_raise(meeting, context, db)
    if project_id is not None:
        require_project_role(
            current_user,
            project_id,
            [PROJECT_ROLE_OWNER_KEY, PROJECT_ROLE_COORD_KEY],
            db,
        )
    if review.review_status != "pending":
        raise HTTPException(409, "progress review is not pending")

    if payload.status is not None:
        review.status = payload.status
    if payload.suggested_task_status:
        review.suggested_task_status = payload.suggested_task_status.strip()
    review.review_comment = payload.review_comment.strip()

    task_updated = False
    subtask = db.get(models.SubTask, review.baseline_subtask_id) if review.baseline_subtask_id else None
    parent = db.get(models.Task, subtask.task_id) if subtask else None
    if review.baseline_subtask_id and (not subtask or not parent or parent.project_id != project_id):
        raise HTTPException(409, "review target subtask is not part of this project")

    if subtask:
        before = crud.to_dict(subtask)
        target_status = _progress_status_to_task_status(review.status)
        if target_status and target_status != subtask.status:
            subtask.status = target_status
            task_updated = True
        if review.status == "blocked" and review.evidence_quote:
            note = f"【会议进度阻塞】{review.evidence_quote}"
            subtask.notes = f"{subtask.notes}\n{note}".strip() if subtask.notes else note
            task_updated = True
        after = crud.to_dict(subtask)
        if task_updated:
            crud.log(
                db,
                current_user,
                "meeting_progress_review_confirm",
                "subtask",
                subtask.id,
                before,
                after,
                project_id=project_id,
                note=review.evidence_quote,
            )

    account = db.query(models.Account).filter(models.Account.username == current_user).first()
    review.review_status = "accepted"
    review.reviewer_person_id = account.person_id if account else None
    review.reviewed_at = utc_now()
    db.commit()
    db.refresh(review)
    result = crud.to_dict(review)
    result["task_updated"] = task_updated
    return result


@router.get("/{row_id}/revisions")
def list_meeting_revisions(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")
    project_id = _row_project_id(row, db)
    if row.publish_status != "published" and not _can_view_meeting_draft(row, current_user, context, db):
        raise HTTPException(403, "permission denied")
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    rows = (
        db.query(models.MeetingRevision)
        .filter(models.MeetingRevision.meeting_id == row_id)
        .order_by(models.MeetingRevision.version_no.desc(), models.MeetingRevision.id.desc())
        .all()
    )
    return [crud.to_dict(item) for item in rows]


@router.get("/{row_id}/revisions/{version_no}")
def get_meeting_revision(
    row_id: int,
    version_no: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    rows = list_meeting_revisions(row_id, current_user, db)
    for item in rows:
        if item["version_no"] == version_no:
            return item
    raise HTTPException(404, "meeting revision not found")


def _meeting_for_read(
    row_id: int,
    current_user: str,
    db: Session,
) -> models.Meeting:
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")
    project_id = _row_project_id(row, db)
    if row.publish_status != "published" and not _can_view_meeting_draft(row, current_user, context, db):
        raise HTTPException(403, "permission denied")
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    return row


@router.get("/{row_id}/change-set")
def get_meeting_change_set(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    row = _meeting_for_read(row_id, current_user, db)
    change_set = (
        db.query(models.MeetingChangeSet)
        .filter_by(meeting_id=row.id)
        .first()
    )
    if not change_set:
        raise HTTPException(404, "meeting change set not found")
    return _meeting_change_set_payload(change_set, db)


@router.patch("/{row_id}/change-set/proposals/{proposal_id}")
def patch_meeting_change_proposal(
    row_id: int,
    proposal_id: int,
    payload: schemas.MeetingChangeProposalPatch,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    meeting = _meeting_for_read(row_id, current_user, db)
    change_set = (
        db.query(models.MeetingChangeSet)
        .filter_by(meeting_id=meeting.id)
        .first()
    )
    if not change_set:
        raise HTTPException(404, "meeting change set not found")
    proposal = (
        db.query(models.MeetingChangeProposal)
        .filter_by(id=proposal_id, change_set_id=change_set.id)
        .first()
    )
    if not proposal:
        raise HTTPException(404, "meeting change proposal not found")
    edit_meeting_change_proposal(
        proposal=proposal,
        change_set=change_set,
        transcript_text=meeting.transcript_text or "",
        proposed=payload.proposed,
        evidence=payload.evidence,
        reason=payload.reason,
        db=db,
    )
    db.commit()
    db.refresh(proposal)
    return _meeting_change_proposal_payload(proposal, change_set.project_id)


@router.post("/{row_id}/change-set/execute")
def execute_reviewed_meeting_change_set(
    row_id: int,
    payload: schemas.MeetingChangeSetExecutePayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    meeting = _meeting_for_read(row_id, current_user, db)
    proposals = execute_meeting_change_set(
        meeting=meeting,
        proposal_ids=payload.proposal_ids,
        actor=current_user,
        db=db,
    )
    for proposal in proposals:
        evidence = _json_value(proposal.evidence_json, [])
        proposed = _json_value(proposal.proposed_json, {})
        audit_before = {
            "proposal_id": proposal.id,
            "before": _json_value(proposal.before_json, {}),
            "proposed": proposed,
            "evidence": evidence,
        }
        audit_after = {
            "proposal_id": proposal.id,
            "proposed": proposed,
            "evidence": evidence,
            "result_target_id": proposal.result_target_id,
            "execution_status": proposal.execution_status,
        }
        crud.log(
            db,
            current_user,
            "meeting_change_execute",
            "meeting_change_proposal",
            proposal.id,
            audit_before,
            audit_after,
            project_id=meeting.project_id,
        )
    db.commit()
    change_set = (
        db.query(models.MeetingChangeSet)
        .filter_by(meeting_id=meeting.id)
        .first()
    )
    return _meeting_change_set_payload(change_set, db)


@router.get("/{row_id}")
def get_meeting(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    row = _meeting_for_read(row_id, current_user, db)
    return crud.to_dict(row)


@router.put("/{row_id}")
def update_meeting(
    row_id: int,
    payload: schemas.MeetingPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")

    project_id = _meeting_project_id_or_raise(row, context, db)
    if project_id is not None and not _is_meeting_creator(current_user, context, row):
        require_project_role(
            current_user,
            project_id,
            [PROJECT_ROLE_OWNER_KEY],
            db,
        )

    require_project_business_writable(project_id, db)
    before = crud.to_dict(row)
    update_data = {
        k: v
        for k, v in payload.model_dump().items()
        if k not in {"project_id", "related_special_project"}
    }
    if context.get("is_tech_admin") and payload.project_id is not None:
        row.project_id = payload.project_id
    if context.get("is_tech_admin") and payload.related_special_project:
        row.related_special_project = payload.related_special_project
    append_meeting_revision(
        db,
        row,
        update_data,
        saved_by=current_user,
        preserve_legacy=True,
    )
    crud.log(db, current_user, "meeting_update", "meeting", row.id, before, payload.model_dump())
    db.commit()
    return crud.to_dict(row)


@router.patch("/{row_id}/status")
def patch_meeting_status(
    row_id: int,
    payload: schemas.MeetingStatusPatch,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")

    project_id = _meeting_project_id_or_raise(row, context, db)
    if project_id is not None:
        require_project_role(
            current_user,
            project_id,
            [PROJECT_ROLE_OWNER_KEY],
            db,
        )

    require_project_business_writable(project_id, db)
    allowed = {"draft", "published", "returned"}
    if payload.publish_status not in allowed:
        raise HTTPException(422, f"publish_status must be one of {allowed}")

    before = {"publish_status": row.publish_status}
    row.publish_status = payload.publish_status
    action = {
        "published": "meeting_publish",
        "returned": "meeting_return",
        "draft": "meeting_save_draft",
    }.get(payload.publish_status, "meeting_update_status")
    crud.log(db, current_user, action, "meeting", row.id, before, {"publish_status": payload.publish_status})

    if payload.publish_status == "published":
        from ..services.notify import send as _notify, person_name_for_account
        import json as _json
        caller_name = person_name_for_account(current_user, db)
        project_id = _row_project_id(row, db)
        try:
            action_items = _json.loads(row.task_list_json or "[]")
        except Exception:
            action_items = []
        from ..services.notify import person_id_for_name as _pid_for_name
        import re as _re
        notified: set[str] = set()
        # 向参会人发送已发布会议通知。
        participant_str = row.participants or ""
        participants = [p.strip() for p in _re.split(r"[,??\n]+", participant_str) if p.strip()]
        for p in participants:
            if p != caller_name and p not in notified:
                notified.add(p)
                _notify(db, recipient_id=_pid_for_name(p, db), recipient=p,
                        ntype="meeting_published",
                        title=f"会议已发布：{row.title or '未命名会议'}",
                        body=f"会议《{row.title or '未命名会议'}》已由 {caller_name} 发布，日期：{row.meeting_date or '未填写'}",
                        link=f"/project/{project_id}/meeting" if project_id else "",
                        project_id=project_id)
        # 向需要执行行动项的成员发送任务通知。
        for item in action_items:
            member = (item.get("member") or "").strip()
            if member and member != caller_name and member not in notified:
                notified.add(member)
                _notify(db, recipient_id=_pid_for_name(member, db), recipient=member,
                        ntype="meeting_action",
                        title=f"会议行动项：{row.title or '未命名会议'}",
                        body=f"请处理事项：{item.get('task', '')}，截止时间：{item.get('deadline') or '未填写'}",
                        link=f"/project/{project_id}/meeting" if project_id else "",
                        project_id=project_id)

    db.commit()
    return crud.to_dict(row)


@router.delete("/{row_id}")
def delete_meeting(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")

    project_id = _meeting_project_id_or_raise(row, context, db)
    if project_id is not None:
        require_project_role(current_user, project_id, [PROJECT_ROLE_OWNER_KEY], db)

    require_project_business_writable(project_id, db)
    before = crud.to_dict(row)
    crud.log(db, current_user, "meeting_delete", "meeting", row_id, before, {})
    db.delete(row)
    db.commit()
    return {"ok": True}


class GenerateTaskCardsRequest(BaseModel):
    project_id: int
    transcript_text: str
    speaker_map: dict[str, str]


_PROMPT_TASK_CARDS = """你是会议任务卡生成助手。
请根据 speaker_map、tasks_context 和 text 生成任务卡，只输出严格 JSON，不要输出任何解释。

speaker_map:
{speaker_map}

tasks_context:
{tasks_context}

text:
{text}

输出格式：
{
  "task_cards": [
    {
      "action": "create | update_status | add_note",
      "parent_task_id": 123,
      "subtask_id": 456,
      "title": "任务标题",
      "subtask_title": "子任务标题",
      "assignee": "负责人",
      "plan_time": "YYYY-MM-DD 或空字符串",
      "new_status": "状态值",
      "notes": "补充说明",
      "note": "备注",
      "evidence": "原文证据"
    }
  ]
}

要求：
- 只输出 JSON
- 如果没有可执行任务，返回 {"task_cards": []}
- action 只能是 create、update_status、add_note
- 优先匹配 tasks_context 中已有任务和子任务
- evidence 用原文短句支持判断
"""


def _build_tasks_context(project_id: int, db: Session) -> str:
    tasks = (
        db.query(models.Task)
        .filter(
            models.Task.project_id == project_id,
            models.Task.is_deleted.is_(False),
            models.Task.status.notin_([TS.S_COMPLETED, TS.S_ARCHIVED]),
        )
        .order_by(models.Task.id.asc())
        .all()
    )
    lines: list[str] = []
    for task in tasks:
        lines.append(
            f"关键任务 #{task.id}：{task.key_task}"
            f"｜负责人：{task.owner or '未填写'}｜状态：{task.status or '未填写'}"
        )
        subtasks = (
            db.query(models.SubTask)
            .filter(models.SubTask.task_id == task.id, models.SubTask.is_deleted.is_(False))
            .order_by(models.SubTask.id.asc())
            .all()
        )
        for st in subtasks:
            lines.append(
                f"  - 子任务 #{st.id}：{st.title}"
                f"｜状态：{st.status or '未填写'}｜负责人：{st.assignee or '未填写'}"
            )
    return "\n".join(lines) if lines else "暂无可参考的关键任务"


@router.post("/generate-task-cards")
async def generate_task_cards(
    payload: GenerateTaskCardsRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    current_user = require_login(current_user, db)
    require_project_role(
        current_user,
        payload.project_id,
        [PROJECT_ROLE_OWNER_KEY, PROJECT_ROLE_COORD_KEY],
        db,
    )

    if not payload.transcript_text.strip():
        raise HTTPException(422, "transcript_text 不能为空")
    if not payload.speaker_map:
        raise HTTPException(422, "speaker_map 不能为空")

    tasks_context = _build_tasks_context(payload.project_id, db)
    speaker_context = "\n".join(
        f"{k} = {v}" for k, v in payload.speaker_map.items()
    )
    prompt = _PROMPT_TASK_CARDS.format(
        speaker_map=speaker_context,
        tasks_context=tasks_context,
        text=payload.transcript_text[:12000],
    )

    try:
        result = await asyncio.to_thread(_do_analyze, db, payload.transcript_text, prompt)
    except Exception as exc:
        logger.warning("generate_task_cards failed: %s", exc)
        raise HTTPException(500, f"AI analysis failed: {exc}")

    raw_cards = result.get("task_cards") or []
    enriched: list[dict] = []
    for card in raw_cards:
        action = card.get("action")
        if action in ("update_status", "add_note"):
            sid = card.get("subtask_id")
            if sid:
                row = db.get(models.SubTask, sid)
                if row and not getattr(row, "is_deleted", False):
                    card["current_payload"] = {
                        "title": row.title or "",
                        "assignee": row.assignee or "",
                        "plan_time": row.plan_time or "",
                        "status": row.status or "",
                        "completion_criteria": getattr(row, "completion_criteria", "") or "",
                        "notes": getattr(row, "notes", "") or "",
                    }
        enriched.append(card)

    return {"task_cards": enriched}


_PROMPT_GENERIC = """你是一个只做事实提取的会议纪要助手。请从下面的会议文字中提取结构化信息，只输出 JSON。

只可提取原文明确出现的事实。不得推断、评价、补全或编写原文没有的结论、负责人、截止时间、状态、风险或建议；原文未提及的字段必须留空或返回空数组。不得生成参会人员。

【工作推进表上下文（仅用于理解和核对，不得作为会议事实写入）】
{tasks_context}

【会议文字】
```
{text}
```

输出格式（严格 JSON，没有的字段填空字符串或空数组）：
{{
  "title": "根据内容自动生成会议标题",
  "meeting_type": "weekly/monthly/review/special/discuss/kickoff，选最合适的",
  "meeting_date": "YYYY-MM-DD，未提及则空字符串",
  "host": "主持人姓名，未提及则空字符串",
  "participants": "",
  "summary": "100字以内事实性会议要点",
  "reports": [],
  "confirmed_items": ["会议已明确确认并可直接入库的事项"],
  "decision_requests": ["需要企业教练判断的事项"],
  "action_items": [{{"member": "负责人", "task": "事项", "deadline": "时间或空字符串"}}],
  "change_set": []
}}

要求：
- confirmed_items 仅记录会议原文已明确拍板的结果；没有则空数组
- decision_requests 仅记录原文明确要求企业教练判断、确认或裁定的事项；普通讨论、已拍板结果与待办不得放入此字段
- 负责人或截止时间没有在原文明确出现时，分别填空字符串
- 提供项目 ID 时，change_set 是必填字段；未提出任何可由原文逐字引文支撑的工作推进表变更时，返回 []
- change_set 单项必须严格为：
{{
  "action": "create_workstream|update_workstream|create_subtask|update_subtask",
  "target": {{"project_id": 123, "workstream_id": 456, "subtask_id": 789, "parent_workstream_id": 456}},
  "proposed": {{"允许修改的字段": "字符串值"}},
  "evidence": ["会议转录中的逐字连续引文"],
  "reason": "非空字符串，说明引文如何支持变更",
  "confidence": 0.0
}}
- target 内的 ID 必须是冻结快照中已有的整数；目标不明确时不得猜测任何 ID，省略不确定的 ID 并保留说明；evidence 必须是会议转录中的逐字连续片段。
"""

# 项目汇报会提示词（有发言人映射 + 成员上下文时使用）
_PROMPT_REPORT = """你是一个只做事实提取的会议纪要助手。

只可依据下方“会议转录文字”中明确出现的内容生成纪要。不得推断、评价、补全或润色为原文未表达的结论；不得生成参会人员。不能生成进度状态、角色、领导反馈、风险判断或常识性建议，除非原文逐项明确说明。会议要点只能复述原文的议题、已明确结论和待办，不能判断“整体按计划”“进展顺利”等原文未出现的状态。原文未提及的字段必须留空或返回空数组。

【工作推进表上下文（仅用于理解和核对，不得作为会议事实写入）】
{member_context}

【会议转录文字】
```
{text}
```

【提取要求】
这是一场项目推进汇报会，每位成员依次汇报本期进展，领导进行点评和指导。

对每位汇报人，请提取：
1. 本期完成了什么（结合该成员"上次计划"对比，判断完成情况）
2. 遇到的问题或卡点
3. 请求领导协助或需要决策的事项
4. 领导对该人的反馈（分三类）：
   - 肯定的内容
   - 需要改进的地方
   - 补充提醒（汇报人没提到但领导专门指出的盲点，这个非常重要不能遗漏）
5. 该人宣布的下一步计划（含时间节点）

注意：
- "领导"角色的发言内容是评价和指导，不是汇报，不要给他生成报告条目
- 区分"已完成"和"进行中"，汇报人说"基本完成""差不多了"属于"部分完成"
- 如果汇报人的任务与上次计划对不上，要在 vs_last_plan 中说明

严格输出 JSON，不要任何解释：
{{
  "title": "会议标题",
  "meeting_type": "weekly/monthly/review/special/discuss/kickoff",
  "meeting_date": "YYYY-MM-DD或空字符串",
  "host": "主持人姓名",
  "participants": "",
  "summary": "100字以内会议要点，只复述原文明确出现的议题、结论和待办，不作状态判断",
  "reports": [
    {{
      "member": "成员姓名",
      "content": "该成员在本次会议中明确说出的进度更新；无实际更新不得生成该成员对象",
      "related_task": "仅可填写工作推进表中可精确关联的任务名称；无法精确关联则空字符串"
    }}
  ],
  "confirmed_items": ["会议已明确确认并可直接入库的事项"],
  "decision_requests": ["需要企业教练判断的事项"],
  "action_items": [{{"member": "负责人", "task": "事项", "deadline": "时间或空字符串"}}],
  "change_set": []
}}

提供项目 ID 时，change_set 是必填字段；未提出任何可由原文逐字引文支撑的工作推进表变更时，返回 []。
change_set 单项必须严格为：
{{
  "action": "create_workstream|update_workstream|create_subtask|update_subtask",
  "target": {{"project_id": 123, "workstream_id": 456, "subtask_id": 789, "parent_workstream_id": 456}},
  "proposed": {{"允许修改的字段": "字符串值"}},
  "evidence": ["会议转录中的逐字连续引文"],
  "reason": "非空字符串，说明引文如何支持变更",
  "confidence": 0.0
}}
target 内的 ID 必须是冻结快照中已有的整数；目标不明确时不得猜测任何 ID，省略不确定的 ID 并保留说明；evidence 必须是会议转录中的逐字连续片段。
"""




def _fetch_member_context(member_name: str, project_id: int, db: Session) -> dict:
    """查询该成员当前任务列表和上次提交的 next_steps。"""
    from sqlalchemy import or_
    from .. import models as m

    tasks = (
        db.query(m.Task)
        .filter(
            m.Task.project_id == project_id,
            or_(m.Task.owner == member_name, m.Task.collaborators.contains(member_name)),
            m.Task.status.notin_(["已完成"]),
        )
        .order_by(m.Task.plan_time)
        .limit(8)
        .all()
    )

    last_sub = (
        db.query(m.UpdateSubmission)
        .filter(
            m.UpdateSubmission.project_id == project_id,
            m.UpdateSubmission.submitter == member_name,
        )
        .order_by(m.UpdateSubmission.created_at.desc())
        .first()
    )

    next_steps: list[str] = []
    if last_sub:
        for field in (last_sub.human_result_json, last_sub.ai_result_json):
            if not field:
                continue
            try:
                data = json.loads(field)
                ns = data.get("next_steps") or []
                next_steps = [str(s) for s in ns if s]
                if next_steps:
                    break
            except Exception:
                pass

    return {
        "name": member_name,
        "tasks": [
            {
                "task": t.key_task,
                "status": t.status,
                "plan_time": t.plan_time or "",
                "problem": t.problem_note or "",
            }
            for t in tasks
        ],
        "last_next_steps": next_steps,
    }


def _build_member_context_text(
    speaker_map: dict[str, str],
    speaker_roles: dict[str, str],
    project_id: int,
    db: Session,
) -> str:
    lines: list[str] = []
    seen: set[str] = set()

    for speaker, name in speaker_map.items():
        role = speaker_roles.get(speaker, "其他")
        label = f"{speaker}（{name}，{role}）" if name else f"{speaker}（{role}）"

        if role == "领导":
            lines.append(f"- {label}：负责对汇报内容进行点评和指导，无需生成汇报条目")
            continue

        if not name or name in seen:
            lines.append(f"- {label}")
            continue
        seen.add(name)

        ctx = _fetch_member_context(name, project_id, db)

        block = [f"- {label}"]
        if ctx["last_next_steps"]:
            block.append(f"  上次计划的下一步：")
            for ns in ctx["last_next_steps"][:5]:
                block.append(f"    · {ns}")
        else:
            block.append(f"  上次计划：（无记录）")

        if ctx["tasks"]:
            block.append(f"  当前进行中任务：")
            for t in ctx["tasks"]:
                status_str = f"[{t['status']}]" if t["status"] else ""
                time_str = f"，计划{t['plan_time']}" if t["plan_time"] else ""
                problem_str = f"，问题：{t['problem']}" if t["problem"] else ""
                block.append(f"    · {t['task']}{status_str}{time_str}{problem_str}")
        lines.extend(block)

    return "\n".join(lines) if lines else "（未提供参会人信息）"


def _build_all_members_context(
    member_names: list[str],
    project_id: int | None,
    db: Session,
) -> str:
    """为 /analyze 端点构建所有项目成员的上下文（无需 speaker_map）。
    
    返回格式化的文本，包含每位成员的：
    - 上次计划的下一步
    - 当前进行中的任务
    """
    if not project_id or not member_names:
        return ""
    
    lines: list[str] = []
    seen: set[str] = set()
    
    for name in member_names:
        name = name.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        
        ctx = _fetch_member_context(name, project_id, db)
        
        block = [f"- {name}"]
        if ctx["last_next_steps"]:
            block.append("  上次计划的下一步：")
            for ns in ctx["last_next_steps"][:5]:
                block.append(f"    · {ns}")
        else:
            block.append("  上次计划：（无记录）")
        
        if ctx["tasks"]:
            block.append("  当前进行中任务：")
            for t in ctx["tasks"]:
                status_str = f"[{t['status']}]" if t["status"] else ""
                time_str = f"，计划{t['plan_time']}" if t["plan_time"] else ""
                problem_str = f"，问题：{t['problem']}" if t["problem"] else ""
                block.append(f"    · {t['task']}{status_str}{time_str}{problem_str}")
        else:
            block.append("  当前任务：（无进行中任务）")
        
        lines.extend(block)
    
    return "\n".join(lines)


def _do_analyze(
    db: Session,
    text: str,
    prompt: str,
    *,
    resource_id: int | None = None,
) -> dict:
    """Invoke the meeting-analysis capability and retain the legacy JSON parser."""
    _ = text
    response = AIService(db).invoke_chat(
        Capability.MEETING_ANALYSIS,
        prompt,
        AIInvocationContext(resource_type="meeting", resource_id=resource_id),
    )
    raw = response.text
    start = raw.find("{")
    if start < 0:
        raise ValueError("LLM did not return a JSON object")
    result, _ = json.JSONDecoder().raw_decode(raw[start:])
    if not isinstance(result, dict):
        raise ValueError("LLM did not return a JSON object")
    return result


