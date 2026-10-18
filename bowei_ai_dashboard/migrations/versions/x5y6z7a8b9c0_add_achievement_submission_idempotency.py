"""Add retry identity to achievement submissions.

Revision ID: x5y6z7a8b9c0
Revises: w4x5y6z7a8b9
"""

from alembic import op
import sqlalchemy as sa


revision = "x5y6z7a8b9c0"
down_revision = "w4x5y6z7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("achievement_submissions") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("request_payload_hash", sa.String(length=64), nullable=True))
        batch.create_index(
            "ix_achievement_submissions_client_request_id",
            ["client_request_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("achievement_submissions") as batch:
        batch.drop_index("ix_achievement_submissions_client_request_id")
        batch.drop_column("request_payload_hash")
        batch.drop_column("client_request_id")
