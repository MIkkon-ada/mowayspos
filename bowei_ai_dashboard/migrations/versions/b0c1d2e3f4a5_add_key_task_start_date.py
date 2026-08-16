"""Add structured Key Task start dates after the workspace base revision.

Revision ID: b0c1d2e3f4a5
Revises: e6f7a8b9c0d1
Create Date: 2026-08-16
"""

from alembic import op
import sqlalchemy as sa


revision = "b0c1d2e3f4a5"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("subtasks") as batch:
        batch.add_column(sa.Column("start_date", sa.Date(), nullable=True))
        batch.create_index("ix_subtasks_start_date", ["start_date"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("subtasks") as batch:
        batch.drop_index("ix_subtasks_start_date")
        batch.drop_column("start_date")
