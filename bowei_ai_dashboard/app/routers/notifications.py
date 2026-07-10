from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..permissions import get_current_user_name
from ..services.notify import person_id_for_account, person_name_for_account

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _get_recipient_filter(username: str, db: Session):
    """
    返回通知查询条件：
    - 优先：recipient_id == person_id（精确，抗改名）
    - 兜底：recipient.in_({username, person_name})（兼容历史记录）
    两个条件取 OR，确保新旧通知都能查到。
    """
    from sqlalchemy import or_
    pid = person_id_for_account(username, db)
    pname = person_name_for_account(username, db)
    names = {username}
    if pname:
        names.add(pname)

    if pid:
        return or_(
            models.Notification.recipient_id == pid,
            models.Notification.recipient.in_(names),
        )
    return models.Notification.recipient.in_(names)


@router.get("/count")
def unread_count(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    count = (
        db.query(models.Notification)
        .filter(
            _get_recipient_filter(current_user, db),
            models.Notification.is_read == False,  # noqa: E712
        )
        .count()
    )
    return {"count": count}


@router.get("")
def list_notifications(
    page: int = 1,
    page_size: int = 20,
    is_read: bool | None = None,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    query = db.query(models.Notification).filter(_get_recipient_filter(current_user, db))
    if is_read is not None:
        query = query.filter(models.Notification.is_read == is_read)
    rows = (
        query.outerjoin(models.Project, models.Project.id == models.Notification.project_id)
        .add_columns(models.Project.name.label("project_name"))
        .order_by(models.Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return [
        {
            "id": notif.id,
            "type": notif.type,
            "title": notif.title,
            "body": notif.body,
            "link": notif.link,
            "is_read": notif.is_read,
            "created_at": notif.created_at.isoformat() if notif.created_at else None,
            "project_id": notif.project_id,
            "project_name": project_name,
        }
        for notif, project_name in rows
    ]


@router.post("/{nid}/read")
def mark_read(
    nid: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    row = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == nid,
            _get_recipient_filter(current_user, db),
        )
        .first()
    )
    if row:
        row.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    (
        db.query(models.Notification)
        .filter(
            _get_recipient_filter(current_user, db),
            models.Notification.is_read == False,  # noqa: E712
        )
        .update({"is_read": True}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True}
