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


def recipient_ids_for(db: Session, schedule: models.ExecutionSchedule, kind: str) -> set[int]:
    if kind == "start":
        return {schedule.assignee_id} if schedule.assignee_id else set()
    subtask = db.get(models.SubTask, schedule.subtask_id)
    task = db.get(models.Task, subtask.task_id) if subtask else None
    if not task or not task.project_id:
        return {schedule.assignee_id} if schedule.assignee_id else set()
    result = {person_id for person_id in (schedule.assignee_id, task.owner_id) if person_id}
    result.update(member.person_id for member in db.query(models.ProjectMember).filter_by(project_id=task.project_id, role="owner").all() if member.person_id)
    return result


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


def scan_execution_schedule_reminders(db: Session, *, today: date) -> int:
    created = 0
    rows = db.query(models.ExecutionSchedule, models.SubTask, models.Task, models.Project).join(
        models.SubTask, models.ExecutionSchedule.subtask_id == models.SubTask.id
    ).join(models.Task, models.SubTask.task_id == models.Task.id).join(
        models.Project, models.Task.project_id == models.Project.id
    ).filter(
        models.ExecutionSchedule.is_deleted.is_(False), models.SubTask.is_deleted.is_(False),
        models.Task.is_deleted.is_(False), models.Project.is_active.is_(True),
    ).all()
    for schedule, _subtask, task, project in rows:
        for kind in reminder_kinds_for(schedule, today):
            link = f"/project/{project.id}/tasks?subtaskId={schedule.subtask_id}&scheduleId={schedule.id}"
            for recipient_id in recipient_ids_for(db, schedule, kind):
                if create_reminder_notification(db, schedule=schedule, recipient_id=recipient_id, kind=kind, due_on=today, project_id=project.id, link=link):
                    created += 1
    db.commit()
    return created
