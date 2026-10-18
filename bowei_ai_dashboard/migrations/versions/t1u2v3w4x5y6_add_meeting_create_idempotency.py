"""Add retry identity to meeting creation requests.

Revision ID: t1u2v3w4x5y6
Revises: s0t1u2v3w4x5
"""

from alembic import op
import sqlalchemy as sa


revision = "t1u2v3w4x5y6"
down_revision = "s0t1u2v3w4x5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("meetings") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("request_payload_hash", sa.String(length=64), nullable=True))
        batch.create_index(
            "ix_meetings_client_request_id",
            ["client_request_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("meetings") as batch:
        batch.drop_index("ix_meetings_client_request_id")
        batch.drop_column("request_payload_hash")
        batch.drop_column("client_request_id")
