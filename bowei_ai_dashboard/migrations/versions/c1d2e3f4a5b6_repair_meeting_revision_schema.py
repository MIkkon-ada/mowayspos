"""repair meeting revision schema for databases upgraded before f0 was complete

Revision ID: c1d2e3f4a5b6
Revises: f0a1b2c3d4e5
"""

from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def _create_index_if_missing(table_name: str, column: str) -> None:
    bind = op.get_bind()
    index_name = f"ix_{table_name}_{column}"
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, [column])


def upgrade() -> None:
    """Backfill tables and fields omitted by the originally released f0 migration.

    The checks make this a no-op for fresh databases, where the corrected f0
    migration has already created the complete schema.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "meeting_transcript_sources" not in tables:
        op.create_table(
            "meeting_transcript_sources",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id")),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("source_hash", sa.String(64), nullable=False),
            sa.Column("source_type", sa.String(20), nullable=False),
            sa.Column("created_by_person_id", sa.Integer(), sa.ForeignKey("people.id")),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )
    if "meeting_transcript_revisions" not in tables:
        op.create_table(
            "meeting_transcript_revisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("meeting_transcript_sources.id"), nullable=False),
            sa.Column("revision_no", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("text_hash", sa.String(64), nullable=False),
            sa.Column("created_by_person_id", sa.Integer(), sa.ForeignKey("people.id")),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.UniqueConstraint("source_id", "revision_no", name="uq_meeting_transcript_revision"),
        )
    if "meeting_analysis_runs" not in tables:
        op.create_table(
            "meeting_analysis_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id")),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("meeting_transcript_sources.id"), nullable=False),
            sa.Column("transcript_revision_id", sa.Integer(), sa.ForeignKey("meeting_transcript_revisions.id")),
            *[sa.Column(name, sa.Text(), nullable=False) for name in ("member_snapshot_json", "plan_snapshot_json", "agent_input_json", "raw_response_json", "normalized_output_json", "validation_output_json")],
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("model_name", sa.String(120), nullable=False),
            sa.Column("policy_version", sa.String(64), nullable=False),
            sa.Column("prompt_version", sa.String(64), nullable=False),
            sa.Column("prompt_hash", sa.String(64), nullable=False),
            sa.Column("input_hash", sa.String(64), nullable=False),
            sa.Column("reference_at", sa.DateTime(), nullable=False),
            sa.Column("timezone", sa.String(64), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("created_by_person_id", sa.Integer(), sa.ForeignKey("people.id")),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )
    if "meeting_analysis_candidates" not in tables:
        op.create_table(
            "meeting_analysis_candidates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("meeting_analysis_runs.id"), nullable=False),
            sa.Column("candidate_type", sa.String(32), nullable=False),
            *[sa.Column(name, sa.Text(), nullable=False) for name in ("agent_proposal_json", "evidence_json", "validation_json", "final_value_json")],
            sa.Column("validation_status", sa.String(24), nullable=False),
            sa.Column("review_status", sa.String(24), nullable=False),
            sa.Column("reviewer_person_id", sa.Integer(), sa.ForeignKey("people.id")),
            sa.Column("review_comment", sa.Text()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )

    revision_columns = {column["name"] for column in sa.inspect(bind).get_columns("meeting_revisions")}
    for column in (
        sa.Column("transcript_source_id", sa.Integer(), sa.ForeignKey("meeting_transcript_sources.id")),
        sa.Column("transcript_revision_id", sa.Integer(), sa.ForeignKey("meeting_transcript_revisions.id")),
        sa.Column("analysis_run_id", sa.Integer(), sa.ForeignKey("meeting_analysis_runs.id")),
        sa.Column("parent_revision_id", sa.Integer(), sa.ForeignKey("meeting_revisions.id")),
        sa.Column("revision_kind", sa.String(length=32)),
        sa.Column("agent_output_json", sa.Text()),
        sa.Column("validation_output_json", sa.Text()),
        sa.Column("human_output_json", sa.Text()),
        sa.Column("human_diff_json", sa.Text()),
    ):
        if column.name not in revision_columns:
            op.add_column("meeting_revisions", column)

    for table_name, columns in {
        "meeting_transcript_sources": ("id", "meeting_id", "source_hash"),
        "meeting_transcript_revisions": ("id", "source_id"),
        "meeting_analysis_runs": ("id", "project_id", "meeting_id", "source_id", "transcript_revision_id", "status", "created_by_person_id"),
        "meeting_analysis_candidates": ("id", "run_id", "candidate_type", "validation_status", "review_status", "reviewer_person_id"),
        "meeting_revisions": ("id", "meeting_id", "transcript_source_id", "transcript_revision_id", "analysis_run_id", "parent_revision_id"),
    }.items():
        for column in columns:
            _create_index_if_missing(table_name, column)


def downgrade() -> None:
    # The prior f0 downgrade removes the repaired schema.  This revision only
    # brings already-upgraded databases to f0's intended logical schema.
    pass
