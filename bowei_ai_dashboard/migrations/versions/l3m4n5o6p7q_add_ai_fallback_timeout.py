"""Add fallback-specific AI policy request timeouts.

Revision ID: l3m4n5o6p7q
Revises: k2l3m4n5o6p7
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa


revision = "l3m4n5o6p7q"
down_revision = "k2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_capability_policies",
        sa.Column("fallback_timeout_seconds", sa.Integer(), nullable=False, server_default="25"),
    )
    op.execute(
        sa.text(
            "UPDATE ai_capability_policies "
            "SET fallback_timeout_seconds = 25 "
            "WHERE fallback_timeout_seconds IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE ai_capability_policies "
            "SET timeout_seconds = 200 "
            "WHERE capability_key = 'project.init.analysis'"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("ai_capability_policies") as batch:
        batch.drop_column("fallback_timeout_seconds")
