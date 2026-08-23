"""Controlled reconciliation for databases missing optional schedule tables."""

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from .. import models


_SCHEDULE_FIELDS = {
    "id",
    "subtask_id",
    "plan_type",
    "plan_month",
    "title",
    "start_date",
    "due_date",
    "assignee",
    "assignee_id",
    "status",
    "expected_output",
    "collaborator_ids",
    "completion_criteria",
    "progress_note",
    "risk_dependency",
    "actual_output",
    "delay_reason",
    "sort_order",
    "reminder_policy",
    "created_by",
    "updated_by",
    "is_deleted",
    "created_at",
    "updated_at",
}


def reconcile_execution_schedule_schema(connection: Connection) -> str:
    """Create only wholly-missing schedule tables; reject partial schemas."""
    inspector = inspect(connection)
    has_schedules = inspector.has_table("execution_schedules")
    has_reminders = inspector.has_table("execution_schedule_reminders")

    if has_schedules:
        present_fields = {column["name"] for column in inspector.get_columns("execution_schedules")}
        missing_fields = sorted(_SCHEDULE_FIELDS - present_fields)
        if missing_fields:
            raise RuntimeError(
                "execution_schedules exists but is incomplete: " + ", ".join(missing_fields)
            )
    elif has_reminders:
        raise RuntimeError("execution_schedule_reminders exists without execution_schedules")
    else:
        models.ExecutionSchedule.__table__.create(connection, checkfirst=False)

    if not inspect(connection).has_table("execution_schedule_reminders"):
        models.ExecutionScheduleReminder.__table__.create(connection, checkfirst=False)

    return "created" if not has_schedules else "already_ready"
