"""Persist project batch import retry results.

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8
"""

from alembic import op
import sqlalchemy as sa


revision = "w4x5y6z7a8b9"
down_revision = "v3w4x5y6z7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_batch_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_request_id", sa.String(length=64), nullable=False),
        sa.Column("request_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_batch_imports_id", "project_batch_imports", ["id"])
    op.create_index(
        "ix_project_batch_imports_client_request_id",
        "project_batch_imports",
        ["client_request_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_project_batch_imports_client_request_id", table_name="project_batch_imports")
    op.drop_index("ix_project_batch_imports_id", table_name="project_batch_imports")
    op.drop_table("project_batch_imports")
