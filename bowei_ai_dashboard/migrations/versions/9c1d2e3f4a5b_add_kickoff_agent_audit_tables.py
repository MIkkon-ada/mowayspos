"""add kickoff Agent audit tables

Revision ID: 9c1d2e3f4a5b
Revises: f1a2b3c4d5e6
"""

from alembic import op
import sqlalchemy as sa


revision = "9c1d2e3f4a5b"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kickoff_agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id"), nullable=True),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_kickoff_agent_runs_id", "kickoff_agent_runs", ["id"])
    op.create_index("ix_kickoff_agent_runs_project_id", "kickoff_agent_runs", ["project_id"])
    op.create_index("ix_kickoff_agent_runs_meeting_id", "kickoff_agent_runs", ["meeting_id"])
    op.create_index("ix_kickoff_agent_runs_status", "kickoff_agent_runs", ["status"])
    op.create_index("ix_kickoff_agent_runs_created_by_person_id", "kickoff_agent_runs", ["created_by_person_id"])
    op.create_table(
        "kickoff_change_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("kickoff_agent_runs.id"), nullable=False),
        sa.Column("proposal_type", sa.String(length=20), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("before_json", sa.Text(), nullable=False),
        sa.Column("proposed_json", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("validation_json", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("reviewer_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_kickoff_change_proposals_id", "kickoff_change_proposals", ["id"])
    op.create_index("ix_kickoff_change_proposals_run_id", "kickoff_change_proposals", ["run_id"])
    op.create_index("ix_kickoff_change_proposals_target_id", "kickoff_change_proposals", ["target_id"])
    op.create_index("ix_kickoff_change_proposals_review_status", "kickoff_change_proposals", ["review_status"])
    op.create_index("ix_kickoff_change_proposals_reviewer_person_id", "kickoff_change_proposals", ["reviewer_person_id"])


def downgrade() -> None:
    op.drop_table("kickoff_change_proposals")
    op.drop_table("kickoff_agent_runs")
