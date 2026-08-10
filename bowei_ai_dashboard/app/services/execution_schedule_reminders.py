from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .. import models
from ..services import notify

CHINA = ZoneInfo("Asia/Shanghai")
ONE_DAY = timedelta(days=1)
FINAL_STATUSES = {"已完成", "已取消"}


def reminder_kinds_for(schedule: models.ExecutionSchedule, today: date) -> set[str]:
    if schedule.is_deleted or schedule.status in FINAL_STATUSES:
        return set()
    result: set[str] = set()
    if schedule.start_date == today:
        result.add("start")
    if schedule.due_date == today + ONE_DAY:
        result.add("due_soon")
    if schedule.due_date < today:
        result.add("overdue")
    return result


def notification_type(kind: str) -> str:
    return f"execution_schedule_{kind}"


def create_reminder_notification(db: Session, *, schedule: models.ExecutionSchedule, recipient_id: int, kind: str, due_on: date, project_id: int, link: str) -> bool:
    existing = db.query(models.ExecutionScheduleReminder).filter_by(
        schedule_id=schedule.id, reminder_kind=kind, due_on=due_on, recipient_id=recipient_id,
    ).first()
    if existing:
        return False
    reminder = models.ExecutionScheduleReminder(
        schedule_id=schedule.id, reminder_kind=kind, due_on=due_on, recipient_id=recipient_id,
    )
    db.add(reminder)
    notify.send(
        db, recipient_id=recipient_id, ntype=notification_type(kind),
        title=f"执行安排提醒：{schedule.title}", body=f"截止日期：{schedule.due_date.isoformat()}",
        link=link, project_id=project_id,
    )
    db.flush()
    return True
