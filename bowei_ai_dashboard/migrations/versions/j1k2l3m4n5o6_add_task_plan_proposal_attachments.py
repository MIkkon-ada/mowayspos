"""Add persisted task-plan proposal attachments.

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa


revision = "j1k2l3m4n5o6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_plan_proposal_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("task_plan_proposal_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("uploaded_by_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    for name, columns in (
        ("ix_task_plan_proposal_attachments_run_id", ["run_id"]),
        ("ix_task_plan_proposal_attachments_content_hash", ["content_hash"]),
        ("ix_task_plan_proposal_attachments_uploaded_by_person_id", ["uploaded_by_person_id"]),
    ):
        op.create_index(name, "task_plan_proposal_attachments", columns)


def downgrade() -> None:
    op.drop_table("task_plan_proposal_attachments")
