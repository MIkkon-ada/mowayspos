"""Add retry identity to manual issue creation requests.

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
"""

from alembic import op
import sqlalchemy as sa


revision = "r9s0t1u2v3w4"
down_revision = "q8r9s0t1u2v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("issues") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("request_payload_hash", sa.String(length=64), nullable=True))
        batch.create_index(
            "ix_issues_client_request_id",
            ["client_request_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("issues") as batch:
        batch.drop_index("ix_issues_client_request_id")
        batch.drop_column("request_payload_hash")
        batch.drop_column("client_request_id")
