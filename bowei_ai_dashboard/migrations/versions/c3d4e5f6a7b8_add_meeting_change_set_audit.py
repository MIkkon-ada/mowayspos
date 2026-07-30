"""add meeting change set audit tables

Revision ID: c3d4e5f6a7b8
Revises: e8f9a0b1c2d3
"""

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meeting_change_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id"), nullable=True),
        sa.Column("created_by_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("transcript_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_meeting_change_sets_project_id_status",
        "meeting_change_sets",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_meeting_change_sets_meeting_id",
        "meeting_change_sets",
        ["meeting_id"],
    )

    op.create_table(
        "meeting_change_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "change_set_id",
            sa.Integer(),
            sa.ForeignKey("meeting_change_sets.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("parent_workstream_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("before_json", sa.Text(), nullable=False),
        sa.Column("proposed_json", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("validation_json", sa.Text(), nullable=False),
        sa.Column("execution_status", sa.String(length=20), nullable=False),
        sa.Column("executed_by_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("result_target_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_meeting_change_proposals_change_set_id_execution_status",
        "meeting_change_proposals",
        ["change_set_id", "execution_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_meeting_change_proposals_change_set_id_execution_status",
        table_name="meeting_change_proposals",
    )
    op.drop_table("meeting_change_proposals")
    op.drop_index("ix_meeting_change_sets_meeting_id", table_name="meeting_change_sets")
    op.drop_index(
        "ix_meeting_change_sets_project_id_status",
        table_name="meeting_change_sets",
    )
    op.drop_table("meeting_change_sets")
