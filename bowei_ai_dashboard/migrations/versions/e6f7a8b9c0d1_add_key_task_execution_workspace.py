"""Add the Key Task execution workspace projection and semantic fields.

Revision ID: e6f7a8b9c0d1
Revises: b8c9d0e1f2a3
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "e6f7a8b9c0d1"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("subtasks") as batch:
        batch.add_column(sa.Column("collaborator_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("due_kind", sa.String(length=10), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("due_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("due_label", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("due_reference_date", sa.Date(), nullable=True))
        batch.create_index("ix_subtasks_due_kind", ["due_kind"], unique=False)
        batch.create_index("ix_subtasks_due_date", ["due_date"], unique=False)
        batch.create_index("ix_subtasks_due_reference_date", ["due_reference_date"], unique=False)

    with op.batch_alter_table("execution_schedules") as batch:
        batch.add_column(sa.Column("due_kind", sa.String(length=10), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("due_label", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("due_reference_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_index("ix_execution_schedules_due_kind", ["due_kind"], unique=False)
        batch.create_index("ix_execution_schedules_due_reference_date", ["due_reference_date"], unique=False)
        batch.create_index("ix_execution_schedules_is_archived", ["is_archived"], unique=False)

    op.execute("UPDATE execution_schedules SET due_kind = 'exact' WHERE due_date IS NOT NULL")
    op.execute("UPDATE execution_schedules SET due_kind = 'unknown' WHERE due_date IS NULL")

    # Deterministic lineage repair only: exactly one active Key Task identifies the submission.
    # SQLite stores booleans as 0/1, whereas PostgreSQL requires boolean operands.
    active_subtask_predicate = "COALESCE(s.is_deleted, 0) = 0"
    if op.get_bind().dialect.name != "sqlite":
        active_subtask_predicate = "COALESCE(s.is_deleted, false) = false"
    op.execute(
        f"""
        UPDATE update_submissions
        SET related_subtask_id = (
            SELECT MIN(s.id) FROM subtasks AS s
            WHERE s.source_submission_id = update_submissions.id
              AND {active_subtask_predicate}
        )
        WHERE related_subtask_id IS NULL
          AND 1 = (
            SELECT COUNT(*) FROM subtasks AS s
            WHERE s.source_submission_id = update_submissions.id
              AND {active_subtask_predicate}
          )
        """
    )
    op.execute(
        """
        UPDATE update_submissions
        SET related_task_id = (
            SELECT s.task_id FROM subtasks AS s
            WHERE s.id = update_submissions.related_subtask_id
        )
        WHERE related_subtask_id IS NOT NULL
          AND related_task_id IS NULL
        """
    )

    op.create_table(
        "key_task_execution_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("key_task_id", sa.Integer(), sa.ForeignKey("subtasks.id"), nullable=False),
        sa.Column("execution_plan_id", sa.Integer(), sa.ForeignKey("execution_schedules.id"), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("actor_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("actor_name_snapshot", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.Column("effective_at", sa.DateTime(), nullable=False),
        sa.Column("affects_current_progress", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status_before", sa.String(length=40), nullable=True),
        sa.Column("status_after", sa.String(length=40), nullable=True),
        sa.Column("progress_summary", sa.Text(), nullable=True),
        sa.Column("next_step", sa.Text(), nullable=True),
        sa.Column("display_payload_json", sa.Text(), nullable=True),
        sa.Column("authority", sa.String(length=30), nullable=False, server_default="confirmed"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("dedupe_key", name="uq_key_task_execution_event_dedupe_key"),
    )
    for name, columns in (
        ("ix_key_task_execution_events_id", ["id"]),
        ("ix_key_task_execution_events_project_id", ["project_id"]),
        ("ix_key_task_execution_events_key_task_id", ["key_task_id"]),
        ("ix_key_task_execution_events_execution_plan_id", ["execution_plan_id"]),
        ("ix_key_task_execution_events_event_type", ["event_type"]),
        ("ix_key_task_execution_events_source_type", ["source_type"]),
        ("ix_key_task_execution_events_source_id", ["source_id"]),
        ("ix_key_task_execution_events_actor_person_id", ["actor_person_id"]),
        ("ix_key_task_execution_events_occurred_at", ["occurred_at"]),
        ("ix_key_task_execution_events_confirmed_at", ["confirmed_at"]),
        ("ix_key_task_execution_events_effective_at", ["effective_at"]),
        ("ix_key_task_execution_events_authority", ["authority"]),
        ("ix_key_task_execution_events_created_at", ["created_at"]),
        ("ix_key_task_execution_events_affects_current_progress", ["affects_current_progress"]),
        ("ix_key_task_execution_events_current_progress", ["key_task_id", "authority", "affects_current_progress", "effective_at", "id"]),
        ("ix_key_task_execution_events_timeline", ["key_task_id", "occurred_at", "id"]),
    ):
        op.create_index(name, "key_task_execution_events", columns, unique=False)


def downgrade() -> None:
    op.drop_table("key_task_execution_events")
    with op.batch_alter_table("execution_schedules") as batch:
        batch.drop_index("ix_execution_schedules_is_archived")
        batch.drop_index("ix_execution_schedules_due_reference_date")
        batch.drop_index("ix_execution_schedules_due_kind")
        batch.drop_column("is_archived")
        batch.drop_column("due_reference_date")
        batch.drop_column("due_label")
        batch.drop_column("due_kind")
    with op.batch_alter_table("subtasks") as batch:
        batch.drop_index("ix_subtasks_due_reference_date")
        batch.drop_index("ix_subtasks_due_date")
        batch.drop_index("ix_subtasks_due_kind")
        batch.drop_column("due_reference_date")
        batch.drop_column("due_label")
        batch.drop_column("due_date")
        batch.drop_column("due_kind")
        batch.drop_column("collaborator_ids")
