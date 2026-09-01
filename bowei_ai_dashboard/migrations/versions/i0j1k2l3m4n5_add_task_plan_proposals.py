"""Add persisted AI task-plan proposal runs.

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m
Create Date: 2026-08-31
"""

from alembic import op
import sqlalchemy as sa


revision = "i0j1k2l3m4n5"
down_revision = "h9i0j1k2l3m"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_plan_proposal_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("key_task_id", sa.Integer(), sa.ForeignKey("subtasks.id"), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready_for_review"),
        sa.Column("model_code", sa.String(length=96), nullable=False, server_default=""),
        sa.Column("invocation_log_id", sa.Integer(), sa.ForeignKey("ai_invocation_logs.id"), nullable=True),
        sa.Column("created_by_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    for name, columns in (
        ("ix_task_plan_proposal_runs_project_id", ["project_id"]),
        ("ix_task_plan_proposal_runs_key_task_id", ["key_task_id"]),
        ("ix_task_plan_proposal_runs_source_hash", ["source_hash"]),
        ("ix_task_plan_proposal_runs_status", ["status"]),
        ("ix_task_plan_proposal_runs_invocation_log_id", ["invocation_log_id"]),
        ("ix_task_plan_proposal_runs_created_by_person_id", ["created_by_person_id"]),
        ("ix_task_plan_proposal_runs_project_key_task_status", ["project_id", "key_task_id", "status"]),
    ):
        op.create_index(name, "task_plan_proposal_runs", columns)
    op.create_table(
        "task_plan_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("task_plan_proposal_runs.id"), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("validation_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="needs_confirmation"),
        sa.Column("reviewer_edit_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_plan_id", sa.Integer(), sa.ForeignKey("execution_schedules.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    for name, columns in (
        ("ix_task_plan_proposals_run_id", ["run_id"]),
        ("ix_task_plan_proposals_status", ["status"]),
        ("ix_task_plan_proposals_created_plan_id", ["created_plan_id"]),
        ("ix_task_plan_proposals_run_status", ["run_id", "status"]),
    ):
        op.create_index(name, "task_plan_proposals", columns)


def downgrade() -> None:
    op.drop_table("task_plan_proposals")
    op.drop_table("task_plan_proposal_runs")
