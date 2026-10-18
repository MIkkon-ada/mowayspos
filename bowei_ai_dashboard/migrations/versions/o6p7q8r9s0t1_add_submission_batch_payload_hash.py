"""Bind submission batch idempotency keys to their request payload.

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
"""

from alembic import op
import sqlalchemy as sa


revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "update_submission_batches",
        sa.Column("request_payload_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("update_submission_batches", "request_payload_hash")
