"""Add key-task risk marker fields and merge current migration heads.

Revision ID: f8a9b0c1d2e3
Revises: b0c1d2e3f4a5, d5e6f7a8b9c0
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa


revision = "f8a9b0c1d2e3"
down_revision = "g8h9i0j1k2l"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("subtasks") as batch:
        batch.add_column(sa.Column("risk_note", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("risk_marked_by", sa.String(length=50), nullable=False, server_default=""))
        batch.add_column(sa.Column("risk_marked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("subtasks") as batch:
        batch.drop_column("risk_marked_at")
        batch.drop_column("risk_marked_by")
        batch.drop_column("risk_note")
