"""Add retry identity to workstream creation requests.

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
"""

from alembic import op
import sqlalchemy as sa


revision = "q8r9s0t1u2v3"
down_revision = "p7q8r9s0t1u2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("request_payload_hash", sa.String(length=64), nullable=True))
        batch.create_index(
            "ix_tasks_client_request_id",
            ["client_request_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.drop_index("ix_tasks_client_request_id")
        batch.drop_column("request_payload_hash")
        batch.drop_column("client_request_id")
