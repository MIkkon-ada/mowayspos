"""add meeting skill clarification runtime

Revision ID: f5a6b7c8d9e0
Revises: f4a5b6c7d8e9
"""

from alembic import op
import sqlalchemy as sa


revision = "f5a6b7c8d9e0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meeting_skill_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=True),
        sa.Column("skill_name", sa.String(length=96), nullable=False),
        sa.Column("skill_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("current_input_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("output_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("output_answer_revisions_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_by_person_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"]),
        sa.ForeignKeyConstraint(["created_by_person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meeting_skill_runs_project_id", "meeting_skill_runs", ["project_id"])
    op.create_index("ix_meeting_skill_runs_meeting_id", "meeting_skill_runs", ["meeting_id"])
    op.create_index("ix_meeting_skill_runs_skill_name", "meeting_skill_runs", ["skill_name"])
    op.create_index("ix_meeting_skill_runs_status", "meeting_skill_runs", ["status"])
    op.create_index("ix_meeting_skill_runs_current_input_snapshot_id", "meeting_skill_runs", ["current_input_snapshot_id"])
    op.create_index("ix_meeting_skill_runs_created_by_person_id", "meeting_skill_runs", ["created_by_person_id"])

    op.create_table(
        "meeting_skill_input_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("reference_files_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["meeting_skill_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "version", name="uq_meeting_skill_snapshot_version"),
    )
    op.create_index("ix_meeting_skill_input_snapshots_run_id", "meeting_skill_input_snapshots", ["run_id"])
    op.create_index("ix_meeting_skill_input_snapshots_input_hash", "meeting_skill_input_snapshots", ["input_hash"])
    op.create_index("ix_meeting_skill_input_snapshots_is_current", "meeting_skill_input_snapshots", ["is_current"])

    op.create_table(
        "meeting_skill_clarifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("input_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=96), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("question_kind", sa.String(length=40), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("action", sa.String(length=32), nullable=False, server_default="answer"),
        sa.Column("answer_mode", sa.String(length=32), nullable=True),
        sa.Column("allow_other", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_omit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("options_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["meeting_skill_runs.id"]),
        sa.ForeignKeyConstraint(["input_snapshot_id"], ["meeting_skill_input_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meeting_skill_clarifications_run_id", "meeting_skill_clarifications", ["run_id"])
    op.create_index("ix_meeting_skill_clarifications_input_snapshot_id", "meeting_skill_clarifications", ["input_snapshot_id"])
    op.create_index("ix_meeting_skill_clarifications_code", "meeting_skill_clarifications", ["code"])
    op.create_index("ix_meeting_skill_clarifications_question_kind", "meeting_skill_clarifications", ["question_kind"])
    op.create_index("ix_meeting_skill_clarifications_blocking", "meeting_skill_clarifications", ["blocking"])

    op.create_table(
        "meeting_skill_clarification_answer_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("answer_revision", sa.Integer(), nullable=False),
        sa.Column("answer_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("answered_by_person_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["question_id"], ["meeting_skill_clarifications.id"]),
        sa.ForeignKeyConstraint(["answered_by_person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "answer_revision", name="uq_meeting_skill_answer_revision"),
    )
    op.create_index("ix_meeting_skill_clarification_answer_revisions_question_id", "meeting_skill_clarification_answer_revisions", ["question_id"])
    op.create_index("ix_meeting_skill_clarification_answer_revisions_answered_by_person_id", "meeting_skill_clarification_answer_revisions", ["answered_by_person_id"])

    op.create_table(
        "meeting_skill_resolved_facts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=96), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("display_value", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("answer_revision_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["meeting_skill_runs.id"]),
        sa.ForeignKeyConstraint(["answer_revision_id"], ["meeting_skill_clarification_answer_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "field_name", name="uq_meeting_skill_resolved_fact"),
    )
    op.create_index("ix_meeting_skill_resolved_facts_run_id", "meeting_skill_resolved_facts", ["run_id"])
    op.create_index("ix_meeting_skill_resolved_facts_answer_revision_id", "meeting_skill_resolved_facts", ["answer_revision_id"])


def downgrade() -> None:
    op.drop_index("ix_meeting_skill_resolved_facts_answer_revision_id", table_name="meeting_skill_resolved_facts")
    op.drop_index("ix_meeting_skill_resolved_facts_run_id", table_name="meeting_skill_resolved_facts")
    op.drop_table("meeting_skill_resolved_facts")
    op.drop_index("ix_meeting_skill_clarification_answer_revisions_answered_by_person_id", table_name="meeting_skill_clarification_answer_revisions")
    op.drop_index("ix_meeting_skill_clarification_answer_revisions_question_id", table_name="meeting_skill_clarification_answer_revisions")
    op.drop_table("meeting_skill_clarification_answer_revisions")
    op.drop_index("ix_meeting_skill_clarifications_blocking", table_name="meeting_skill_clarifications")
    op.drop_index("ix_meeting_skill_clarifications_question_kind", table_name="meeting_skill_clarifications")
    op.drop_index("ix_meeting_skill_clarifications_code", table_name="meeting_skill_clarifications")
    op.drop_index("ix_meeting_skill_clarifications_input_snapshot_id", table_name="meeting_skill_clarifications")
    op.drop_index("ix_meeting_skill_clarifications_run_id", table_name="meeting_skill_clarifications")
    op.drop_table("meeting_skill_clarifications")
    op.drop_index("ix_meeting_skill_input_snapshots_is_current", table_name="meeting_skill_input_snapshots")
    op.drop_index("ix_meeting_skill_input_snapshots_input_hash", table_name="meeting_skill_input_snapshots")
    op.drop_index("ix_meeting_skill_input_snapshots_run_id", table_name="meeting_skill_input_snapshots")
    op.drop_table("meeting_skill_input_snapshots")
    op.drop_index("ix_meeting_skill_runs_created_by_person_id", table_name="meeting_skill_runs")
    op.drop_index("ix_meeting_skill_runs_current_input_snapshot_id", table_name="meeting_skill_runs")
    op.drop_index("ix_meeting_skill_runs_status", table_name="meeting_skill_runs")
    op.drop_index("ix_meeting_skill_runs_skill_name", table_name="meeting_skill_runs")
    op.drop_index("ix_meeting_skill_runs_meeting_id", table_name="meeting_skill_runs")
    op.drop_index("ix_meeting_skill_runs_project_id", table_name="meeting_skill_runs")
    op.drop_table("meeting_skill_runs")
