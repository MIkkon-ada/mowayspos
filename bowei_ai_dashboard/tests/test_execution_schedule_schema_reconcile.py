from sqlalchemy import create_engine, inspect

from app import models
from app.database import Base
from app.services.execution_schedule_schema import reconcile_execution_schedule_schema


def test_reconcile_creates_missing_execution_schedule_tables_with_month_plan_fields():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        models.ExecutionScheduleReminder.__table__.drop(connection)
        models.ExecutionSchedule.__table__.drop(connection)
        result = reconcile_execution_schedule_schema(connection)

    inspector = inspect(engine)
    fields = {column["name"] for column in inspector.get_columns("execution_schedules")}

    assert result == "created"
    assert {"plan_month", "expected_output", "collaborator_ids", "delay_reason", "sort_order"}.issubset(fields)
    assert inspector.has_table("execution_schedule_reminders")
