"""Add project work progress columns and key task extension fields.

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q
"""

from alembic import op
import sqlalchemy as sa

revision = "m4n5o6p7q8r9"
down_revision = "l3m4n5o6p7q"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("work_progress_optional_columns", sa.JSON(), nullable=False, server_default="[]"))
    for column in ("expected_outcome", "goal", "bowei_role"):
        op.add_column("subtasks", sa.Column(column, sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    bind = op.get_bind()
    configured_columns = bind.execute(sa.text(
        "SELECT 1 FROM projects "
        "WHERE COALESCE(CAST(work_progress_optional_columns AS TEXT), '[]') "
        "NOT IN ('[]', 'null') LIMIT 1"
    )).first()
    populated_key_task_fields = bind.execute(sa.text(
        "SELECT 1 FROM subtasks "
        "WHERE COALESCE(expected_outcome, '') <> '' "
        "OR COALESCE(goal, '') <> '' "
        "OR COALESCE(bowei_role, '') <> '' LIMIT 1"
    )).first()
    if configured_columns or populated_key_task_fields:
        raise RuntimeError("work progress data would be lost")

    with op.batch_alter_table("subtasks") as batch:
        for column in ("bowei_role", "goal", "expected_outcome"):
            batch.drop_column(column)
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("work_progress_optional_columns")
