"""add_person_id_to_business_tables

Revision ID: d14986ccb2dd
Revises: 614f43813210
Create Date: 2026-06-23 11:15:34.251828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd14986ccb2dd'
down_revision: Union[str, Sequence[str], None] = '614f43813210'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BOOTSTRAP_MARKER_TABLE = "_moways_migration_bootstrap"
BOOTSTRAP_MARKER_TOKEN = "POST_D149_PRE_4BF_BOOTSTRAP_V1"
DOWNGRADE_UNSUPPORTED_MESSAGE = (
    "Downgrade below d14986ccb2dd is unsupported because the "
    "pre-d149 schema cannot be reconstructed safely."
)


def _consume_valid_bootstrap_marker() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if BOOTSTRAP_MARKER_TABLE not in inspector.get_table_names():
        return False

    columns = inspector.get_columns(BOOTSTRAP_MARKER_TABLE)
    if [column["name"] for column in columns] != ["id", "token"]:
        raise RuntimeError("Invalid bootstrap marker: unexpected column layout.")

    id_column, token_column = columns
    primary_key_columns = tuple(
        inspector.get_pk_constraint(BOOTSTRAP_MARKER_TABLE).get(
            "constrained_columns"
        )
        or ()
    )
    if (
        not isinstance(id_column["type"], sa.Integer)
        or bool(id_column.get("nullable"))
        or primary_key_columns != ("id",)
    ):
        raise RuntimeError("Invalid bootstrap marker: id column does not match.")
    if (
        not isinstance(token_column["type"], sa.String)
        or token_column["type"].length != 100
        or bool(token_column.get("nullable"))
    ):
        raise RuntimeError("Invalid bootstrap marker: token column does not match.")

    unique_constraints = inspector.get_unique_constraints(BOOTSTRAP_MARKER_TABLE)
    if not any(
        tuple(constraint.get("column_names") or ()) == ("token",)
        for constraint in unique_constraints
    ):
        raise RuntimeError("Invalid bootstrap marker: token must be unique.")

    marker = sa.table(
        BOOTSTRAP_MARKER_TABLE,
        sa.column("id", sa.Integer()),
        sa.column("token", sa.String(length=100)),
    )
    rows = list(bind.execute(sa.select(marker.c.id, marker.c.token)))
    if rows != [(1, BOOTSTRAP_MARKER_TOKEN)]:
        raise RuntimeError("Invalid bootstrap marker: expected one exact token row.")

    op.drop_table(BOOTSTRAP_MARKER_TABLE)
    return True


def upgrade() -> None:
    if _consume_valid_bootstrap_marker():
        return
    _upgrade_legacy_schema()


def _upgrade_legacy_schema() -> None:
    # --- tasks ---
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
        # drop old indexes (batch mode will try to carry them over otherwise)
        batch_op.drop_index('idx_tasks_owner_person_id')
        batch_op.drop_index('idx_tasks_project_id')
        batch_op.create_index('ix_tasks_owner_id', ['owner_id'], unique=False)
        batch_op.create_index('ix_tasks_project_id', ['project_id'], unique=False)
        batch_op.create_index('ix_tasks_source_submission_id', ['source_submission_id'], unique=False)
        batch_op.create_index('ix_tasks_is_deleted', ['is_deleted'], unique=False)
        batch_op.create_index('ix_tasks_delete_batch_id', ['delete_batch_id'], unique=False)
        batch_op.create_foreign_key('fk_tasks_owner_id_people', 'people', ['owner_id'], ['id'])
        # drop stale columns from old schema
        batch_op.drop_column('task_code')
        batch_op.drop_column('owner_person_id')
        batch_op.drop_column('coordinator_person_id')

    # --- achievements ---
    with op.batch_alter_table('achievements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
        batch_op.drop_index('idx_achievements_project_id')
        batch_op.create_index('ix_achievements_owner_id', ['owner_id'], unique=False)
        batch_op.create_index('ix_achievements_project_id', ['project_id'], unique=False)
        batch_op.create_index('ix_achievements_source_submission_id', ['source_submission_id'], unique=False)
        batch_op.create_index('ix_achievements_source_achievement_submission_id', ['source_achievement_submission_id'], unique=False)
        batch_op.create_foreign_key('fk_achievements_owner_id_people', 'people', ['owner_id'], ['id'])
        batch_op.drop_column('approved_by_person_id')
        batch_op.drop_column('owner_person_id')
        batch_op.drop_column('approved_at')
        batch_op.drop_column('is_desensitized')

    # --- issues ---
    with op.batch_alter_table('issues', schema=None) as batch_op:
        batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
        batch_op.drop_index('idx_issues_project_id')
        batch_op.create_index('ix_issues_owner_id', ['owner_id'], unique=False)
        batch_op.create_index('ix_issues_project_id', ['project_id'], unique=False)
        batch_op.create_index('ix_issues_source_submission_id', ['source_submission_id'], unique=False)
        batch_op.create_foreign_key('fk_issues_owner_id_people', 'people', ['owner_id'], ['id'])
        batch_op.drop_column('feedback_result')
        batch_op.drop_column('owner_person_id')
        batch_op.drop_column('issue_code')
        batch_op.drop_column('need_decision_by_person_id')
        batch_op.drop_column('helper_person_id')
        batch_op.drop_column('feedback_required')

    # --- update_submissions ---
    with op.batch_alter_table('update_submissions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('submitter_id', sa.Integer(), nullable=True))
        batch_op.drop_index('idx_update_submissions_submitter_person_id')
        batch_op.drop_index('idx_update_submissions_project_id')
        batch_op.create_index('ix_update_submissions_submitter_id', ['submitter_id'], unique=False)
        batch_op.create_index('ix_update_submissions_project_id', ['project_id'], unique=False)
        batch_op.create_foreign_key('fk_upd_sub_submitter_id_people', 'people', ['submitter_id'], ['id'])
        batch_op.drop_column('target_owner_person_id')
        batch_op.drop_column('workflow_status')
        batch_op.drop_column('current_handler_person_id')
        batch_op.drop_column('feedback_to_submitter')
        batch_op.drop_column('ceo_decision_required')
        batch_op.drop_column('parent_submission_id')
        batch_op.drop_column('confirmed_by_person_id')
        batch_op.drop_column('submitter_person_id')

    # --- achievement_submissions (no stale columns) ---
    with op.batch_alter_table('achievement_submissions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('submitter_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_achievement_submissions_submitter_id', ['submitter_id'], unique=False)
        batch_op.create_foreign_key('fk_ach_sub_submitter_id_people', 'people', ['submitter_id'], ['id'])

    # --- subtasks (no stale columns) ---
    with op.batch_alter_table('subtasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assignee_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_subtasks_assignee_id', ['assignee_id'], unique=False)
        batch_op.create_foreign_key('fk_subtasks_assignee_id_people', 'people', ['assignee_id'], ['id'])

    # --- subtask_drafts (no stale columns) ---
    with op.batch_alter_table('subtask_drafts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assignee_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_subtask_drafts_assignee_id', ['assignee_id'], unique=False)
        batch_op.create_foreign_key('fk_subtask_drafts_assignee_id_people', 'people', ['assignee_id'], ['id'])

    # --- people: drop stale columns, rename index ---
    with op.batch_alter_table('people', schema=None) as batch_op:
        batch_op.drop_index('idx_people_system_role')
        batch_op.create_index('ix_people_system_role', ['system_role'], unique=False)
        batch_op.drop_column('phone')
        batch_op.drop_column('permission_scope')
        batch_op.drop_column('employee_code')
        batch_op.drop_column('email')
        batch_op.drop_column('title')

    # --- operation_logs: drop stale columns, add index ---
    with op.batch_alter_table('operation_logs', schema=None) as batch_op:
        batch_op.create_index('ix_operation_logs_project_id', ['project_id'], unique=False)
        batch_op.drop_column('remark')
        batch_op.drop_column('operator_person_id')


def downgrade() -> None:
    raise RuntimeError(DOWNGRADE_UNSUPPORTED_MESSAGE)
