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
    op.create_table("meeting_transcript_sources",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id")),
        sa.Column("raw_text", sa.Text(), nullable=False), sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False), sa.Column("created_by_person_id", sa.Integer(), sa.ForeignKey("people.id")),
        sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("meeting_transcript_revisions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("source_id", sa.Integer(), sa.ForeignKey("meeting_transcript_sources.id"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("created_by_person_id", sa.Integer(), sa.ForeignKey("people.id")), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("source_id", "revision_no", name="uq_meeting_transcript_revision"))
    op.create_table("meeting_analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id")), sa.Column("source_id", sa.Integer(), sa.ForeignKey("meeting_transcript_sources.id"), nullable=False),
        sa.Column("transcript_revision_id", sa.Integer(), sa.ForeignKey("meeting_transcript_revisions.id")),
        *[sa.Column(name, sa.Text(), nullable=False) for name in ("member_snapshot_json", "plan_snapshot_json", "agent_input_json", "raw_response_json", "normalized_output_json", "validation_output_json")],
        sa.Column("provider", sa.String(64), nullable=False), sa.Column("model_name", sa.String(120), nullable=False), sa.Column("policy_version", sa.String(64), nullable=False), sa.Column("prompt_version", sa.String(64), nullable=False), sa.Column("prompt_hash", sa.String(64), nullable=False), sa.Column("input_hash", sa.String(64), nullable=False), sa.Column("reference_at", sa.DateTime(), nullable=False), sa.Column("timezone", sa.String(64), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_by_person_id", sa.Integer(), sa.ForeignKey("people.id")), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("meeting_analysis_candidates",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("run_id", sa.Integer(), sa.ForeignKey("meeting_analysis_runs.id"), nullable=False),
        sa.Column("candidate_type", sa.String(32), nullable=False), *[sa.Column(name, sa.Text(), nullable=False) for name in ("agent_proposal_json", "evidence_json", "validation_json", "final_value_json")],
        sa.Column("validation_status", sa.String(24), nullable=False), sa.Column("review_status", sa.String(24), nullable=False), sa.Column("reviewer_person_id", sa.Integer(), sa.ForeignKey("people.id")), sa.Column("review_comment", sa.Text()), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    for table, columns in {
        "meeting_transcript_sources": ("id", "meeting_id", "source_hash"),
        "meeting_transcript_revisions": ("id", "source_id"),
        "meeting_analysis_runs": ("id", "project_id", "meeting_id", "source_id", "transcript_revision_id", "status", "created_by_person_id"),
        "meeting_analysis_candidates": ("id", "run_id", "candidate_type", "validation_status", "review_status", "reviewer_person_id"),
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
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
        sa.Column("transcript_source_id", sa.Integer(), sa.ForeignKey("meeting_transcript_sources.id"), nullable=True),
        sa.Column("transcript_revision_id", sa.Integer(), sa.ForeignKey("meeting_transcript_revisions.id"), nullable=True),
        sa.Column("analysis_run_id", sa.Integer(), sa.ForeignKey("meeting_analysis_runs.id"), nullable=True),
        sa.Column("parent_revision_id", sa.Integer(), sa.ForeignKey("meeting_revisions.id"), nullable=True),
        sa.Column("revision_kind", sa.String(length=32), nullable=True),
        sa.Column("agent_output_json", sa.Text(), nullable=True),
        sa.Column("validation_output_json", sa.Text(), nullable=True),
        sa.Column("human_output_json", sa.Text(), nullable=True),
        sa.Column("human_diff_json", sa.Text(), nullable=True),
        sa.UniqueConstraint("meeting_id", "version_no", name="uq_meeting_revisions_meeting_version"),
    )
    op.create_index("ix_meeting_revisions_id", "meeting_revisions", ["id"])
    op.create_index("ix_meeting_revisions_meeting_id", "meeting_revisions", ["meeting_id"])
    for column in ("transcript_source_id", "transcript_revision_id", "analysis_run_id", "parent_revision_id"):
        op.create_index(f"ix_meeting_revisions_{column}", "meeting_revisions", [column])


def downgrade() -> None:
    for column in ("parent_revision_id", "analysis_run_id", "transcript_revision_id", "transcript_source_id"):
        op.drop_index(f"ix_meeting_revisions_{column}", table_name="meeting_revisions")
    op.drop_index("ix_meeting_revisions_meeting_id", table_name="meeting_revisions")
    op.drop_index("ix_meeting_revisions_id", table_name="meeting_revisions")
    # meeting_revisions holds foreign keys to the analysis and transcript tables.
    # PostgreSQL requires it to be removed before those referenced tables.
    op.drop_table("meeting_revisions")
    for table, columns in {
        "meeting_analysis_candidates": ("reviewer_person_id", "review_status", "validation_status", "candidate_type", "run_id", "id"),
        "meeting_analysis_runs": ("created_by_person_id", "status", "transcript_revision_id", "source_id", "meeting_id", "project_id", "id"),
        "meeting_transcript_revisions": ("source_id", "id"),
        "meeting_transcript_sources": ("source_hash", "meeting_id", "id"),
    }.items():
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
    op.drop_table("meeting_analysis_candidates")
    op.drop_table("meeting_analysis_runs")
    op.drop_table("meeting_transcript_revisions")
    op.drop_table("meeting_transcript_sources")
