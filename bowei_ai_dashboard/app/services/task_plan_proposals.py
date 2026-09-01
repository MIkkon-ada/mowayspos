"""AI task-plan drafting that remains review-only until a user applies it."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from os import PathLike
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..ai.contracts import AIInvocationContext, Capability
from ..ai.service import AIService
from ..time_utils import utc_now
from .key_task_execution import record_execution_event
from .meeting_document_text import MeetingDocumentTextError, extract_meeting_document_text
from .task_plan_proposal_attachments import (
    TaskPlanProposalAttachmentError,
    remove_task_plan_attachment,
    save_task_plan_attachments,
)
from ..routers.monthly_plans import _validate_people

MAX_PROPOSALS = 20
MAX_SOURCE_TEXT_LENGTH = 40_000


@dataclass(frozen=True)
class UploadedAttachment:
    filename: str
    content: bytes


class TaskPlanProposalAttachmentCleanupError(RuntimeError):
    """Raised when project purge cannot safely remove task-plan attachment blobs."""


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse_response(value: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "AI 返回格式无法解析，请重试") from exc
    plans = payload.get("plans") if isinstance(payload, dict) else None
    if not isinstance(plans, list):
        raise HTTPException(422, "AI 未返回计划草稿")
    return [item for item in plans[:MAX_PROPOSALS] if isinstance(item, dict)]


def _quoted(source: str, evidence: dict[str, Any], field: str) -> bool:
    quote = evidence.get(field)
    return isinstance(quote, str) and bool(quote.strip()) and quote.strip() in source


def _normalise_plan(raw: dict[str, Any], source: str, member_ids: set[int]) -> tuple[dict[str, Any], dict[str, Any], str]:
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    title = str(raw.get("title") or "").strip()
    expected_output = str(raw.get("expected_output") or "").strip()
    assignee_id = raw.get("assignee_id")
    collaborator_ids = raw.get("collaborator_ids") if isinstance(raw.get("collaborator_ids"), list) else []
    collaborator_ids = [item for item in collaborator_ids if isinstance(item, int) and not isinstance(item, bool)]
    plan = {
        "title": title,
        "expected_output": expected_output,
        "assignee_id": assignee_id if isinstance(assignee_id, int) and not isinstance(assignee_id, bool) else None,
        "collaborator_ids": collaborator_ids,
        "status": str(raw.get("status") or "未开始").strip() or "未开始",
        "start_date": raw.get("start_date") or None,
        "due_date": raw.get("due_date") or None,
        "completion_criteria": str(raw.get("completion_criteria") or ""),
    }
    issues: list[str] = []
    if not title or not _quoted(source, evidence, "title"):
        issues.append("计划事项缺少可核验原文依据")
    if not expected_output or not _quoted(source, evidence, "expected_output"):
        issues.append("预期成果缺少可核验原文依据")
    if plan["assignee_id"] not in member_ids or not _quoted(source, evidence, "assignee_id"):
        issues.append("负责人需要人工确认")
    if any(person_id not in member_ids for person_id in collaborator_ids):
        issues.append("协助人不属于项目成员")
    for field in ("start_date", "due_date", "completion_criteria"):
        if plan[field] and not _quoted(source, evidence, field):
            issues.append(f"{field} 缺少可核验原文依据")
    state = "ready" if not issues else "needs_confirmation"
    return plan, {"state": state, "errors": issues}, state


def _prompt(source_text: str, members: list[dict[str, Any]]) -> str:
    return f"""你是项目任务拆解助手。只基于给定原文，为一个已选定的关键任务生成最多 {MAX_PROPOSALS} 条可执行任务计划草稿；不要写入系统。
原文：\n{source_text}\n
项目成员（只能使用其中的 id）：{json.dumps(members, ensure_ascii=False)}
只输出 JSON：{{\"plans\":[{{\"title\":\"\",\"expected_output\":\"\",\"assignee_id\":null,\"collaborator_ids\":[],\"status\":\"未开始\",\"start_date\":null,\"due_date\":null,\"completion_criteria\":\"\",\"evidence\":{{\"title\":\"原文精确片段\",\"expected_output\":\"原文精确片段\",\"assignee_id\":\"原文精确片段\",\"start_date\":\"原文精确片段\",\"due_date\":\"原文精确片段\",\"completion_criteria\":\"原文精确片段\"}}}}]}}。没有明确依据的字段留空。"""


def create_text_plan_proposal_run(
    *,
    project_id: int,
    key_task_id: int,
    source_text: str,
    created_by_person_id: int | None,
    actor: str,
    db: Session,
    ai_service: AIService | Any | None = None,
) -> models.TaskPlanProposalRun:
    return create_attachment_plan_proposal_run(
        project_id=project_id,
        key_task_id=key_task_id,
        source_text=source_text,
        attachments=[],
        storage_root="data/task_plan_proposal_attachments",
        created_by_person_id=created_by_person_id,
        actor=actor,
        db=db,
        ai_service=ai_service,
    )


def create_attachment_plan_proposal_run(
    *,
    project_id: int,
    key_task_id: int,
    source_text: str,
    attachments: list[UploadedAttachment],
    storage_root: str | PathLike[str],
    created_by_person_id: int | None,
    actor: str,
    db: Session,
    ai_service: AIService | Any | None = None,
) -> models.TaskPlanProposalRun:
    manual_text = (source_text or "").strip()
    extracted_attachments: list[tuple[UploadedAttachment, str]] = []
    try:
        for attachment in attachments:
            extracted_attachments.append((
                attachment,
                extract_meeting_document_text(attachment.filename, attachment.content),
            ))
    except (AttributeError, MeetingDocumentTextError) as exc:
        raise HTTPException(422, str(exc)) from exc

    sections: list[str] = []
    if manual_text:
        sections.append(f"手工补充文字：\n{manual_text}")
    sections.extend(
        f"附件：{attachment.filename}\n{extracted_text}"
        for attachment, extracted_text in extracted_attachments
    )
    text = "\n\n".join(sections)
    if not text:
        raise HTTPException(422, "请输入需要拆解的文本或上传附件")
    if len(text) > MAX_SOURCE_TEXT_LENGTH:
        raise HTTPException(422, "文本和附件提取内容不能超过 40000 字符")

    saved_attachments: list[dict[str, Any]] = []
    completed = False
    try:
        saved_attachments = save_task_plan_attachments(
            storage_root,
            project_id=project_id,
            attachments=[(attachment.filename, attachment.content) for attachment, _ in extracted_attachments],
        )
        member_rows = db.query(models.ProjectMember).filter_by(project_id=project_id).all()
        members = [{"id": row.person_id, "name": row.person_name_snapshot} for row in member_rows]
        result = (ai_service or AIService(db)).invoke_chat(
            Capability.TASK_PLAN_PROPOSAL,
            _prompt(text, members),
            AIInvocationContext(actor=actor, resource_type="key_task", resource_id=key_task_id),
        )
        raw_plans = _parse_response(result.text)
        run = models.TaskPlanProposalRun(
            project_id=project_id,
            key_task_id=key_task_id,
            source_text=text,
            source_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            status="ready_for_review",
            model_code=result.model_code,
            invocation_log_id=result.invocation_log_id,
            created_by_person_id=created_by_person_id,
        )
        db.add(run)
        db.flush()
        for saved, (_, extracted_text) in zip(saved_attachments, extracted_attachments):
            db.add(models.TaskPlanProposalAttachment(
                run_id=run.id,
                original_name=saved["original_name"],
                storage_key=saved["storage_key"],
                mime_type=saved["mime_type"],
                size_bytes=saved["size_bytes"],
                content_hash=saved["content_hash"],
                extracted_text=extracted_text,
                uploaded_by_person_id=created_by_person_id,
            ))
        member_ids = {item["id"] for item in members}
        for raw in raw_plans:
            plan, validation, status = _normalise_plan(raw, text, member_ids)
            db.add(models.TaskPlanProposal(
                run_id=run.id,
                plan_json=_json_dump(plan),
                evidence_json=_json_dump(raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}),
                validation_json=_json_dump(validation),
                status=status,
            ))
        db.commit()
        completed = True
        return run
    except TaskPlanProposalAttachmentError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    finally:
        if saved_attachments and not completed:
            for saved in reversed(saved_attachments):
                remove_task_plan_attachment(storage_root, saved["storage_key"])


def cleanup_project_task_plan_attachments(
    *, project_id: int, storage_root: str | PathLike[str], db: Session
) -> None:
    """Remove persisted blobs for a project before its attachment rows are deleted."""
    rows = (
        db.query(models.TaskPlanProposalAttachment)
        .join(models.TaskPlanProposalRun, models.TaskPlanProposalAttachment.run_id == models.TaskPlanProposalRun.id)
        .filter(models.TaskPlanProposalRun.project_id == project_id)
        .order_by(models.TaskPlanProposalAttachment.id.asc())
        .all()
    )
    try:
        for row in rows:
            remove_task_plan_attachment(storage_root, row.storage_key)
    except Exception as exc:
        raise TaskPlanProposalAttachmentCleanupError("无法清理任务计划附件") from exc


def _json_load(value: str, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    return parsed


def apply_text_plan_proposals(
    *,
    run: models.TaskPlanProposalRun,
    proposal_ids: list[int],
    actor: str,
    actor_person_id: int | None,
    db: Session,
) -> list[models.ExecutionSchedule]:
    if not proposal_ids or len(proposal_ids) != len(set(proposal_ids)):
        raise HTTPException(422, "请至少选择一条且不重复的计划草稿")
    key_task = db.get(models.SubTask, run.key_task_id)
    task = db.get(models.Task, key_task.task_id) if key_task else None
    if not key_task or not task or key_task.is_deleted or task.is_deleted or task.project_id != run.project_id:
        raise HTTPException(409, "关键任务已变化，无法创建计划")
    if key_task.status == "已完成":
        raise HTTPException(409, "已完成的关键任务必须先重新打开，才能新增任务计划")
    proposals = (
        db.query(models.TaskPlanProposal)
        .filter(models.TaskPlanProposal.run_id == run.id, models.TaskPlanProposal.id.in_(proposal_ids))
        .with_for_update()
        .all()
    )
    if len(proposals) != len(proposal_ids):
        raise HTTPException(404, "计划草稿不存在")
    candidates: list[tuple[models.TaskPlanProposal, schemas.MonthPlanCreatePayload, dict[int, models.Person]]] = []
    for proposal in proposals:
        if proposal.status != "ready":
            raise HTTPException(422, "存在待确认或已处理的计划草稿")
        values = _json_load(proposal.plan_json, {})
        if not isinstance(values, dict):
            raise HTTPException(422, "计划草稿格式无效")
        try:
            payload = schemas.MonthPlanCreatePayload(**values)
        except Exception as exc:
            raise HTTPException(422, "计划草稿字段无效") from exc
        people = _validate_people(run.project_id, payload.assignee_id, payload.collaborator_ids, db)
        candidates.append((proposal, payload, people))
    created: list[models.ExecutionSchedule] = []
    try:
        for proposal, payload, people in candidates:
            data = payload.model_dump()
            data["assignee"] = people[payload.assignee_id].name
            row = models.ExecutionSchedule(
                subtask_id=key_task.id,
                plan_type="month",
                created_by=actor,
                updated_by=actor,
                **data,
            )
            db.add(row)
            db.flush()
            log = crud.log(
                db, actor, "ai_task_plan_proposal_apply", "execution_schedule", row.id,
                {}, crud.to_dict(row), project_id=run.project_id,
            )
            db.flush()
            now = utc_now()
            record_execution_event(
                db,
                project_id=run.project_id,
                key_task_id=key_task.id,
                execution_plan_id=row.id,
                event_type="execution_plan_created",
                source_type="task_plan_proposal",
                source_id=proposal.id,
                dedupe_key=f"operation_log:{log.id}:ai-task-plan-proposal-apply",
                actor_person_id=actor_person_id,
                actor_name=actor,
                occurred_at=now,
                confirmed_at=now,
                effective_at=now,
                affects_current_progress=False,
                status_after=row.status,
                progress_summary=f"AI 建议确认后新增任务计划：{row.title}",
            )
            proposal.created_plan_id = row.id
            proposal.status = "executed"
            created.append(row)
        run.status = "completed"
        db.commit()
    except Exception:
        db.rollback()
        raise
    return created
