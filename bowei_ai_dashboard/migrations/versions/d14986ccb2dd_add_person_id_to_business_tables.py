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


def upgrade() -> None:
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
    with op.batch_alter_table('operation_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('operator_person_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('remark', sa.TEXT(), server_default=sa.text("('')"), nullable=True))
        batch_op.drop_index('ix_operation_logs_project_id')

    with op.batch_alter_table('people', schema=None) as batch_op:
        batch_op.add_column(sa.Column('title', sa.VARCHAR(length=100), nullable=True))
        batch_op.add_column(sa.Column('email', sa.VARCHAR(length=100), nullable=True))
        batch_op.add_column(sa.Column('employee_code', sa.VARCHAR(length=50), nullable=True))
        batch_op.add_column(sa.Column('permission_scope', sa.VARCHAR(length=30), server_default=sa.text("'self'"), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.VARCHAR(length=50), nullable=True))
        batch_op.drop_index('ix_people_system_role')
        batch_op.create_index('idx_people_system_role', ['system_role'], unique=False)

    with op.batch_alter_table('subtask_drafts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_subtask_drafts_assignee_id_people', type_='foreignkey')
        batch_op.drop_index('ix_subtask_drafts_assignee_id')
        batch_op.drop_column('assignee_id')

    with op.batch_alter_table('subtasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_subtasks_assignee_id_people', type_='foreignkey')
        batch_op.drop_index('ix_subtasks_assignee_id')
        batch_op.drop_column('assignee_id')

    with op.batch_alter_table('achievement_submissions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_ach_sub_submitter_id_people', type_='foreignkey')
        batch_op.drop_index('ix_achievement_submissions_submitter_id')
        batch_op.drop_column('submitter_id')

    with op.batch_alter_table('update_submissions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('submitter_person_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('confirmed_by_person_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('parent_submission_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('ceo_decision_required', sa.BOOLEAN(), server_default=sa.text('0'), nullable=True))
        batch_op.add_column(sa.Column('feedback_to_submitter', sa.TEXT(), server_default=sa.text("('')"), nullable=True))
        batch_op.add_column(sa.Column('current_handler_person_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('workflow_status', sa.VARCHAR(length=30), server_default=sa.text("'pending_owner'"), nullable=True))
        batch_op.add_column(sa.Column('target_owner_person_id', sa.INTEGER(), nullable=True))
        batch_op.drop_constraint('fk_upd_sub_submitter_id_people', type_='foreignkey')
        batch_op.drop_index('ix_update_submissions_submitter_id')
        batch_op.drop_index('ix_update_submissions_project_id')
        batch_op.create_index('idx_update_submissions_submitter_person_id', ['submitter_person_id'], unique=False)
        batch_op.create_index('idx_update_submissions_project_id', ['project_id'], unique=False)
        batch_op.drop_column('submitter_id')

    with op.batch_alter_table('issues', schema=None) as batch_op:
        batch_op.add_column(sa.Column('feedback_required', sa.BOOLEAN(), server_default=sa.text('0'), nullable=True))
        batch_op.add_column(sa.Column('helper_person_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('need_decision_by_person_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('issue_code', sa.VARCHAR(length=50), nullable=True))
        batch_op.add_column(sa.Column('owner_person_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('feedback_result', sa.TEXT(), server_default=sa.text("('')"), nullable=True))
        batch_op.drop_constraint('fk_issues_owner_id_people', type_='foreignkey')
        batch_op.drop_index('ix_issues_source_submission_id')
        batch_op.drop_index('ix_issues_project_id')
        batch_op.drop_index('ix_issues_owner_id')
        batch_op.create_index('idx_issues_project_id', ['project_id'], unique=False)
        batch_op.drop_column('owner_id')

    with op.batch_alter_table('achievements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_desensitized', sa.BOOLEAN(), server_default=sa.text('0'), nullable=True))
        batch_op.add_column(sa.Column('approved_at', sa.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column('owner_person_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('approved_by_person_id', sa.INTEGER(), nullable=True))
        batch_op.drop_constraint('fk_achievements_owner_id_people', type_='foreignkey')
        batch_op.drop_index('ix_achievements_source_achievement_submission_id')
        batch_op.drop_index('ix_achievements_source_submission_id')
        batch_op.drop_index('ix_achievements_project_id')
        batch_op.drop_index('ix_achievements_owner_id')
        batch_op.create_index('idx_achievements_project_id', ['project_id'], unique=False)
        batch_op.drop_column('owner_id')

    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('coordinator_person_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('owner_person_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('task_code', sa.VARCHAR(length=50), nullable=True))
        batch_op.drop_constraint('fk_tasks_owner_id_people', type_='foreignkey')
        batch_op.drop_index('ix_tasks_delete_batch_id')
        batch_op.drop_index('ix_tasks_is_deleted')
        batch_op.drop_index('ix_tasks_source_submission_id')
        batch_op.drop_index('ix_tasks_project_id')
        batch_op.drop_index('ix_tasks_owner_id')
        batch_op.create_index('idx_tasks_project_id', ['project_id'], unique=False)
        batch_op.create_index('idx_tasks_owner_person_id', ['owner_person_id'], unique=False)
        batch_op.drop_column('owner_id')
