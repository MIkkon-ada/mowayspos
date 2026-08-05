import asyncio
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..domain import task_status as TS
from ..database import get_db
from ..llm_config import get_provider_config

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
from ..services.meeting_revisions import append_meeting_revision
from ..services.meeting_traceability import normalize_action_items

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


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
    provider = _pick_provider()
    try:
        package = run_kickoff_agent(
            payload.transcript_text,
            snapshot,
            lambda prompt: _do_analyze(payload.transcript_text, prompt, provider),
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
    project = db.get(models.Project, payload.project_id)
    if project and project.status == "pending_kickoff":
        raise HTTPException(409, "项目待启动会确认，不能创建普通会议")

    project_name = resolve_project_context(
        db,
        project_id=payload.project_id,
        related_special_project=payload.related_special_project,
    )["project_name"] or ""
    data = {
        k: v
        for k, v in payload.model_dump().items()
        if k not in {"project_id", "related_special_project"}
    }
    row = models.Meeting(**data)
    row.project_id = payload.project_id
    account = db.query(models.Account).filter(models.Account.username == current_user).first()
    row.creator_person_id = account.person_id if account else None
    if payload.related_special_project:
        row.related_special_project = payload.related_special_project
    elif project_name:
        row.related_special_project = project_name
    db.add(row)
    db.flush()
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
    mode: str | None = None  # "kickoff" | "progress" | None(自动)
    member_names: list[str] | None = None  # 项目成员姓名列表，用于构建成员上下文


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
        require_project_access(current_user, payload.project_id, db)

    if not payload.text.strip():
        raise HTTPException(422, "text 不能为空")

    # 推进表只提供关联与核对上下文；会议原文仍是唯一的纪要事实来源。
    project_member_names = sorted(_project_member_names(payload.project_id, db))
    work_plan_context = _build_all_members_context(project_member_names, payload.project_id, db)
    member_context_text = work_plan_context
    tasks_context_text = work_plan_context

    has_speakers = bool(re.search(r"\d+", payload.text))

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

    prompt += """
HARD TRACEABILITY RULES:
- Only extract work items, decisions, and risks explicitly supported by the transcript.
- Every action_items entry must include member, task, deadline, acceptance_criteria, and evidence_quote.
- evidence_quote must be a short verbatim quote from the transcript; if unavailable, return 待确认.
- If member, deadline, or acceptance_criteria is not explicit, return 待确认 instead of inferring it.
- Never use project context as evidence for a meeting fact.
"""

    provider = _pick_provider()
    try:
        result = await asyncio.to_thread(_do_analyze, payload.text, prompt, provider)
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

    return {
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


@router.get("/{row_id}")
def get_meeting(
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

    provider = _pick_provider()
    try:
        result = await asyncio.to_thread(_do_analyze, payload.transcript_text, prompt, provider)
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
  "action_items": [{{"member": "负责人", "task": "事项", "deadline": "时间或空字符串"}}]
}}

要求：
- confirmed_items 仅记录会议原文已明确拍板的结果；没有则空数组
- decision_requests 仅记录原文明确要求企业教练判断、确认或裁定的事项；普通讨论、已拍板结果与待办不得放入此字段
- 负责人或截止时间没有在原文明确出现时，分别填空字符串
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
  "action_items": [{{"member": "负责人", "task": "事项", "deadline": "时间或空字符串"}}]
}}
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


def _do_analyze(text: str, prompt: str, provider: str) -> dict:
    if provider == "anthropic":
        import anthropic
        cfg = get_provider_config("anthropic")
        if not cfg.get("api_key"):
            raise ValueError("未配置 Claude API Key")
        client = anthropic.Anthropic(api_key=cfg["api_key"], timeout=90)
        resp = client.messages.create(
            model=cfg["model"],
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text
    else:
        from openai import OpenAI
        cfg = get_provider_config(provider)
        if not cfg.get("api_key"):
            raise ValueError(f"未配置 {provider} API Key")
        client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=90)
        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        raw = resp.choices[0].message.content or ""

    start = raw.find("{")
    if start < 0:
        raise ValueError("LLM 未返回有效 JSON")
    result, _ = json.JSONDecoder().raw_decode(raw[start:])
    if not isinstance(result, dict):
        raise ValueError("LLM 未返回有效 JSON")
    return result


def _pick_provider() -> str:
    for p in ("anthropic", "dashscope", "deepseek", "glm"):
        cfg = get_provider_config(p)
        if cfg.get("api_key") and cfg.get("enabled", False):
            return p
    for p in ("anthropic", "dashscope", "deepseek", "glm"):
        cfg = get_provider_config(p)
        if cfg.get("api_key"):
            return p
    return "anthropic"


