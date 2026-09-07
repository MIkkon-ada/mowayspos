"""Add persisted project-init task process text.

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa


revision = "k2l3m4n5o6p7"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("plan_process", sa.Text(), nullable=True, server_default=""))


def downgrade() -> None:
    op.drop_column("tasks", "plan_process")
