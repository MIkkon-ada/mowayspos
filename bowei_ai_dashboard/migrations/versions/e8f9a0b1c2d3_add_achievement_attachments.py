"""add achievement attachments

Revision ID: e8f9a0b1c2d3
Revises: 1b2c3d4e5f6a
"""

from alembic import op
import sqlalchemy as sa


revision = "e8f9a0b1c2d3"
down_revision = "1b2c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "achievement_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("achievement_id", sa.Integer(), sa.ForeignKey("achievements.id"), nullable=True),
        sa.Column("achievement_submission_id", sa.Integer(), sa.ForeignKey("achievement_submissions.id"), nullable=True),
        sa.Column("storage_key", sa.String(length=255), nullable=False, unique=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.String(length=50), nullable=True),
        sa.Column("uploaded_by_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(length=50), nullable=True, server_default=sa.text("''")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_achievement_attachments_id", "achievement_attachments", ["id"])
    op.create_index("ix_achievement_attachments_project_id", "achievement_attachments", ["project_id"])
    op.create_index("ix_achievement_attachments_achievement_id", "achievement_attachments", ["achievement_id"])
    op.create_index("ix_achievement_attachments_achievement_submission_id", "achievement_attachments", ["achievement_submission_id"])
    op.create_index("ix_achievement_attachments_uploaded_by_person_id", "achievement_attachments", ["uploaded_by_person_id"])


def downgrade() -> None:
    op.drop_index("ix_achievement_attachments_uploaded_by_person_id", table_name="achievement_attachments")
    op.drop_index("ix_achievement_attachments_achievement_submission_id", table_name="achievement_attachments")
    op.drop_index("ix_achievement_attachments_achievement_id", table_name="achievement_attachments")
    op.drop_index("ix_achievement_attachments_project_id", table_name="achievement_attachments")
    op.drop_index("ix_achievement_attachments_id", table_name="achievement_attachments")
    op.drop_table("achievement_attachments")
