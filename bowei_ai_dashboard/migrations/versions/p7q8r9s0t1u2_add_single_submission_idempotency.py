"""Add retry-safe request identity to single-project submissions.

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
"""

from alembic import op
import sqlalchemy as sa


revision = "p7q8r9s0t1u2"
down_revision = "o6p7q8r9s0t1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("update_submissions") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("request_payload_hash", sa.String(length=64), nullable=True))
        batch.create_index(
            "ix_update_submissions_client_request_id",
            ["client_request_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("update_submissions") as batch:
        batch.drop_index("ix_update_submissions_client_request_id")
        batch.drop_column("request_payload_hash")
        batch.drop_column("client_request_id")
