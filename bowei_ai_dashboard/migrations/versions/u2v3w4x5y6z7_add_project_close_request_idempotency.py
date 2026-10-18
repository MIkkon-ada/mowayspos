"""Add retry identity to project close requests.

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
"""

from alembic import op
import sqlalchemy as sa


revision = "u2v3w4x5y6z7"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_close_requests") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("request_payload_hash", sa.String(length=64), nullable=True))
        batch.create_index(
            "ix_project_close_requests_client_request_id",
            ["client_request_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("project_close_requests") as batch:
        batch.drop_index("ix_project_close_requests_client_request_id")
        batch.drop_column("request_payload_hash")
        batch.drop_column("client_request_id")
