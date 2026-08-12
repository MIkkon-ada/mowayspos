"""persist approved kickoff baselines and member progress reviews

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("kickoff_agent_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("approved_snapshot_json", sa.Text(), nullable=False, server_default="{}")
        )
        batch_op.alter_column("approved_snapshot_json", server_default=None)

    op.create_table(
        "meeting_progress_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("baseline_run_id", sa.Integer(), nullable=False),
        sa.Column("baseline_task_id", sa.Integer(), nullable=True),
        sa.Column("baseline_subtask_id", sa.Integer(), nullable=True),
        sa.Column("member_name", sa.String(length=100), nullable=False),
        sa.Column("baseline_snapshot_json", sa.Text(), nullable=False),
        sa.Column("report_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("suggested_task_status", sa.String(length=40), nullable=True),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("reviewer_person_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("validation_json", sa.Text(), nullable=False),
        sa.Column("analysis_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"]),
        sa.ForeignKeyConstraint(["baseline_run_id"], ["kickoff_agent_runs.id"]),
        sa.ForeignKeyConstraint(["baseline_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["baseline_subtask_id"], ["subtasks.id"]),
        sa.ForeignKeyConstraint(["reviewer_person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "meeting_id",
            "analysis_version",
            "member_name",
            "baseline_subtask_id",
            name="uq_meeting_progress_review_version_member_subtask",
        ),
    )
    for column in (
        "id",
        "project_id",
        "meeting_id",
        "baseline_run_id",
        "baseline_task_id",
        "baseline_subtask_id",
        "reviewer_person_id",
        "review_status",
        "status",
        "analysis_version",
    ):
        op.create_index(f"ix_meeting_progress_reviews_{column}", "meeting_progress_reviews", [column])


def downgrade() -> None:
    for column in (
        "analysis_version",
        "status",
        "review_status",
        "reviewer_person_id",
        "baseline_subtask_id",
        "baseline_task_id",
        "baseline_run_id",
        "meeting_id",
        "project_id",
        "id",
    ):
        op.drop_index(f"ix_meeting_progress_reviews_{column}", table_name="meeting_progress_reviews")
    op.drop_table("meeting_progress_reviews")

    with op.batch_alter_table("kickoff_agent_runs", schema=None) as batch_op:
        batch_op.drop_column("approved_snapshot_json")
