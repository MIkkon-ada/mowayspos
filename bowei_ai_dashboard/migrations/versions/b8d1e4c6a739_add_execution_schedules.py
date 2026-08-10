"""add execution schedules

Revision ID: b8d1e4c6a739
Revises: a7d9c3e5f102
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from alembic import op

revision = "b8d1e4c6a739"
down_revision = "a7d9c3e5f102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subtask_id", sa.Integer(), sa.ForeignKey("subtasks.id"), nullable=False),
        sa.Column("plan_type", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("assignee", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("people.id")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="待开始"),
        sa.Column("reminder_policy", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_execution_schedules_subtask_id", "execution_schedules", ["subtask_id"])
    op.create_index("ix_execution_schedules_start_date", "execution_schedules", ["start_date"])
    op.create_index("ix_execution_schedules_due_date", "execution_schedules", ["due_date"])
    op.create_table(
        "execution_schedule_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("execution_schedules.id"), nullable=False),
        sa.Column("reminder_kind", sa.String(length=20), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("notification_id", sa.Integer(), sa.ForeignKey("notifications.id")),
        sa.Column("wecom_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("schedule_id", "reminder_kind", "due_on", "recipient_id", name="uq_execution_schedule_reminder"),
    )


def downgrade() -> None:
    op.drop_table("execution_schedule_reminders")
    op.drop_table("execution_schedules")
