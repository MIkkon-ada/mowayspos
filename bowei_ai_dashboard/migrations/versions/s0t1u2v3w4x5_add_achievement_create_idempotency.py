"""Add retry identity to manual achievement creation requests.

Revision ID: s0t1u2v3w4x5
Revises: r9s0t1u2v3w4
"""

from alembic import op
import sqlalchemy as sa


revision = "s0t1u2v3w4x5"
down_revision = "r9s0t1u2v3w4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("achievements") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("request_payload_hash", sa.String(length=64), nullable=True))
        batch.create_index(
            "ix_achievements_client_request_id",
            ["client_request_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("achievements") as batch:
        batch.drop_index("ix_achievements_client_request_id")
        batch.drop_column("request_payload_hash")
        batch.drop_column("client_request_id")
