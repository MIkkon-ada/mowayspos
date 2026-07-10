from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..permissions import (
    PROJECT_ROLE_OWNER,
    get_all_project_roles,
    get_current_user_name,
    get_user_context_from_db,
    is_project_member,
)
from ..time_utils import utc_now
from ..services.project_resolution import resolve_project_context

router = APIRouter(prefix="/api/achievement-submissions", tags=["achievement-submissions"])

_STATUS_PENDING   = "待确认"
_STATUS_CONFIRMED = "已确认"
_STATUS_REJECTED  = "已退回"
_STATUS_WITHDRAWN = "已撤回"


def _require_owner_or_admin(context: dict, row: models.AchievementSubmission, db: Session) -> None:
    if context.get("is_tech_admin"):
        return
    person_id = context.get("person_id")
    proj_id = resolve_project_context(
        db,
        project_id=row.project_id,
        special_project=row.special_project or "",
    )["project_id"]
    if proj_id is not None and person_id is not None:
        if PROJECT_ROLE_OWNER in set(get_all_project_roles(person_id, proj_id, db)):
            return
    proj_name = (row.special_project or "").strip()
    if proj_name and proj_name in context.get("owned_projects", []):
        return
    raise HTTPException(403, "仅项目负责人或技术管理员可执行此操作")


# ── 端点 ──────────────────────────────────────────────────────

@router.post("")
def create_submission(
    payload: schemas.AchievementSubmissionPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    proj_name = resolve_project_context(db, project_id=payload.project_id)["project_name"]
    if not proj_name:
        raise HTTPException(422, "project_id 无效，找不到对应项目")

    person_id = context.get("person_id")
    if not context.get("is_tech_admin"):
        if person_id is None or not is_project_member(person_id, payload.project_id, db):
            raise HTTPException(403, "仅项目成员可提交成果")

    task_row = db.get(models.Task, payload.related_task_id) if payload.related_task_id else None
    if not task_row:
        raise HTTPException(422, "related_task_id 无效，找不到对应关键任务")

    row = models.AchievementSubmission(
        project_id=payload.project_id,
        special_project=proj_name,
        related_task_id=payload.related_task_id,
        submitter=current_user,
        name=payload.name,
        achievement_type=payload.achievement_type,
        version=payload.version,
        file_link=payload.file_link,
        scenario=payload.scenario,
        reuse_tag=payload.reuse_tag,
        status=_STATUS_PENDING,
        source_type="人工补录",
    )
    db.add(row)
    db.flush()
    crud.log(db, current_user, "提交成果审核", "achievement_submission", row.id, {}, crud.to_dict(row),
             project_id=payload.project_id)
    db.commit()
    db.refresh(row)
    return crud.to_dict(row)


@router.get("")
def list_submissions(
    project_id: int | None = None,
    status: str | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    q = db.query(models.AchievementSubmission)

    if project_id is not None:
        q = q.filter(models.AchievementSubmission.project_id == project_id)

    if not context.get("is_tech_admin"):
        person_name = context.get("name", "")
        owned = context.get("owned_projects", [])
        q = q.filter(
            (models.AchievementSubmission.submitter == person_name) |
            (models.AchievementSubmission.special_project.in_(owned) if owned else False)
        )

    if status:
        q = q.filter(models.AchievementSubmission.status == status)

    rows = q.order_by(models.AchievementSubmission.created_at.desc()).limit(200).all()
    return [crud.to_dict(r) for r in rows]


@router.patch("/{sub_id}/confirm")
def confirm_submission(
    sub_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.AchievementSubmission, sub_id)
    if not row:
        raise HTTPException(404, "submission not found")
    _require_owner_or_admin(context, row, db)

    if row.status != _STATUS_PENDING:
        raise HTTPException(422, f"当前状态 [{row.status}] 不可确认，只有待确认状态可以操作")

    now = utc_now()
    row.status = _STATUS_CONFIRMED
    row.reviewer = current_user
    row.reviewed_at = now

    ach = models.Achievement(
        project_id=row.project_id,
        special_project=row.special_project or "",
        related_task_id=row.related_task_id,
        name=row.name,
        achievement_type=row.achievement_type or "方案",
        version=row.version or "V0.1",
        file_link=row.file_link or "",
        scenario=row.scenario or "",
        reuse_tag=row.reuse_tag or "",
        owner=row.submitter or "",
        status="草稿",
        source_type="人工补录确认",
        confirmed_by=current_user,
        confirmed_at=now,
        source_achievement_submission_id=row.id,
    )
    db.add(ach)
    db.flush()
    crud.log(db, current_user, "确认成果入库", "achievement_submission", row.id,
             {"status": _STATUS_PENDING}, {"status": _STATUS_CONFIRMED},
             project_id=row.project_id)
    if row.submitter and row.submitter != current_user:
        from ..services.notify import send as _notify, person_id_for_account, person_name_for_account
        reviewer_name = person_name_for_account(current_user, db)
        _notify(db, recipient_id=person_id_for_account(row.submitter, db),
                recipient=row.submitter, ntype="achievement_confirmed",
                title=f"你提交的成果已审核通过：{row.name or '（无标题）'}",
                body=f"审核人：{reviewer_name}，成果已正式入库",
                link=f"/project/{row.project_id}/achievements" if row.project_id else "",
                project_id=row.project_id)
    db.commit()
    db.refresh(row)
    db.refresh(ach)
    return {"submission": crud.to_dict(row), "achievement": crud.to_dict(ach)}


@router.patch("/{sub_id}/reject")
def reject_submission(
    sub_id: int,
    payload: schemas.AchievementSubmissionRejectRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.AchievementSubmission, sub_id)
    if not row:
        raise HTTPException(404, "submission not found")
    _require_owner_or_admin(context, row, db)

    if row.status != _STATUS_PENDING:
        raise HTTPException(422, f"当前状态 [{row.status}] 不可退回，只有待确认状态可以操作")

    row.status = _STATUS_REJECTED
    row.reviewer = current_user
    row.reviewed_at = utc_now()
    row.reject_reason = payload.reject_reason or ""
    crud.log(db, current_user, "退回成果", "achievement_submission", row.id,
             {"status": _STATUS_PENDING}, {"status": _STATUS_REJECTED, "reject_reason": row.reject_reason},
             project_id=row.project_id)
    if row.submitter:
        from ..services.notify import send as _notify, person_name_for_account, person_id_for_account
        reviewer_name = person_name_for_account(current_user, db)
        submitter_id = person_id_for_account(row.submitter, db)
        _notify(db, recipient_id=submitter_id, recipient=row.submitter,
                ntype="achievement_rejected",
                title=f"你提交的成果被退回：{row.name or '（无标题）'}",
                body=f"退回原因：{row.reject_reason or '未说明'}，审核人：{reviewer_name}",
                link=f"/project/{row.project_id}/achievements" if row.project_id else "",
                project_id=row.project_id)
    db.commit()
    return crud.to_dict(row)


@router.patch("/{sub_id}/withdraw")
def withdraw_submission(
    sub_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = db.get(models.AchievementSubmission, sub_id)
    if not row:
        raise HTTPException(404, "submission not found")
    if row.submitter != current_user:
        raise HTTPException(403, "只有提交人本人可以撤回")
    if row.status != _STATUS_PENDING:
        raise HTTPException(422, f"当前状态 [{row.status}] 不可撤回，只有待确认状态可以操作")

    row.status = _STATUS_WITHDRAWN
    crud.log(db, current_user, "撤回成果提交", "achievement_submission", row.id,
             {"status": _STATUS_PENDING}, {"status": _STATUS_WITHDRAWN},
             project_id=row.project_id)
    db.commit()
    return crud.to_dict(row)
