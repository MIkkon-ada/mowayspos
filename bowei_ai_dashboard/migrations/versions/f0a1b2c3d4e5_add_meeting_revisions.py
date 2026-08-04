"""add immutable meeting-minutes revisions

Revision ID: f0a1b2c3d4e5
Revises: e8f9a0b1c2d3
"""

from alembic import op
import sqlalchemy as sa


revision = "f0a1b2c3d4e5"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meeting_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("is_legacy_snapshot", sa.Boolean(), nullable=False),
        sa.Column("saved_by", sa.String(length=100), nullable=False),
        sa.Column("saved_at", sa.DateTime(), nullable=False),
        sa.Column("related_special_project", sa.String(length=80), nullable=True),
        sa.Column("meeting_type", sa.String(length=40), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("meeting_date", sa.String(length=20), nullable=True),
        sa.Column("host", sa.String(length=50), nullable=True),
        sa.Column("participants", sa.Text(), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("task_list_json", sa.Text(), nullable=True),
        sa.Column("decision_items_json", sa.Text(), nullable=True),
        sa.Column("risk_items_json", sa.Text(), nullable=True),
        sa.Column("publish_status", sa.String(length=20), nullable=True),
        sa.UniqueConstraint("meeting_id", "version_no", name="uq_meeting_revisions_meeting_version"),
    )
    op.create_index("ix_meeting_revisions_id", "meeting_revisions", ["id"])
    op.create_index("ix_meeting_revisions_meeting_id", "meeting_revisions", ["meeting_id"])


def downgrade() -> None:
    op.drop_index("ix_meeting_revisions_meeting_id", table_name="meeting_revisions")
    op.drop_index("ix_meeting_revisions_id", table_name="meeting_revisions")
    op.drop_table("meeting_revisions")
