"""Persist project-meeting Agent audit data and schedule proposal parent."""

from alembic import op
import sqlalchemy as sa


revision = "c4e5f6a7b8c9"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_meeting_runs") as batch_op:
        batch_op.add_column(sa.Column("stage", sa.String(length=32), nullable=False, server_default="created"))
        batch_op.add_column(sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("prompt_version", sa.String(length=64), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("model_code", sa.String(length=96), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("invocation_log_ids_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("tool_trace_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("raw_responses_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("error_code", sa.String(length=64), nullable=False, server_default=""))
        batch_op.create_index("ix_project_meeting_runs_stage", ["stage"])
        batch_op.create_index("ix_project_meeting_runs_error_code", ["error_code"])

    with op.batch_alter_table("meeting_change_proposals") as batch_op:
        batch_op.add_column(sa.Column("parent_subtask_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_meeting_change_proposals_parent_subtask_id_subtasks",
            "subtasks",
            ["parent_subtask_id"],
            ["id"],
        )
        batch_op.create_index("ix_meeting_change_proposals_parent_subtask_id", ["parent_subtask_id"])


def downgrade() -> None:
    with op.batch_alter_table("meeting_change_proposals") as batch_op:
        batch_op.drop_index("ix_meeting_change_proposals_parent_subtask_id")
        batch_op.drop_constraint("fk_meeting_change_proposals_parent_subtask_id_subtasks", type_="foreignkey")
        batch_op.drop_column("parent_subtask_id")

    with op.batch_alter_table("project_meeting_runs") as batch_op:
        batch_op.drop_index("ix_project_meeting_runs_error_code")
        batch_op.drop_index("ix_project_meeting_runs_stage")
        batch_op.drop_column("error_code")
        batch_op.drop_column("raw_responses_json")
        batch_op.drop_column("tool_trace_json")
        batch_op.drop_column("invocation_log_ids_json")
        batch_op.drop_column("model_code")
        batch_op.drop_column("prompt_version")
        batch_op.drop_column("step_count")
        batch_op.drop_column("stage")
