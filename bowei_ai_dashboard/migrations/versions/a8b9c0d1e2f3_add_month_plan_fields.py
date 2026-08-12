"""add monthly plan fields to execution schedules

Revision ID: a8b9c0d1e2f3
Revises: a6b7c8d9e0f1
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from alembic import op


revision = "a8b9c0d1e2f3"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("execution_schedules") as batch:
        batch.add_column(sa.Column("plan_month", sa.String(length=7), nullable=True))
        batch.add_column(sa.Column("expected_output", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("collaborator_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("completion_criteria", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("progress_note", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("risk_dependency", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("actual_output", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("delay_reason", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
        batch.alter_column("start_date", existing_type=sa.Date(), nullable=True)
        batch.alter_column("due_date", existing_type=sa.Date(), nullable=True)
    op.create_index(
        "ix_execution_schedules_month_plan_lookup",
        "execution_schedules",
        ["subtask_id", "plan_type", "plan_month", "is_deleted"],
    )

    if op.get_bind().dialect.name == "postgresql":
        for column in (
            "expected_output",
            "collaborator_ids",
            "completion_criteria",
            "progress_note",
            "risk_dependency",
            "actual_output",
            "delay_reason",
            "sort_order",
        ):
            op.execute(f"ALTER TABLE execution_schedules ALTER COLUMN {column} DROP DEFAULT")


def downgrade() -> None:
    op.drop_index("ix_execution_schedules_month_plan_lookup", table_name="execution_schedules")
    with op.batch_alter_table("execution_schedules") as batch:
        batch.alter_column("due_date", existing_type=sa.Date(), nullable=False)
        batch.alter_column("start_date", existing_type=sa.Date(), nullable=False)
        batch.drop_column("sort_order")
        batch.drop_column("delay_reason")
        batch.drop_column("actual_output")
        batch.drop_column("risk_dependency")
        batch.drop_column("progress_note")
        batch.drop_column("completion_criteria")
        batch.drop_column("collaborator_ids")
        batch.drop_column("expected_output")
        batch.drop_column("plan_month")
