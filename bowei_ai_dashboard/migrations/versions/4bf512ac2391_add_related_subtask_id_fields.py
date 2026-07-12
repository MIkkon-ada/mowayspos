"""add related_subtask_id fields

将 related_subtask_id (nullable, FK→subtasks.id, indexed) 新增到三张业务表：
- update_submissions
- achievements
- issues

本迁移只加字段，不回填历史数据。历史行 remain NULL，前端展示"未指定关键任务"。

Revision ID: 4bf512ac2391
Revises: d14986ccb2dd
Create Date: 2026-07-13 01:38:11.251379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4bf512ac2391'
down_revision: Union[str, Sequence[str], None] = 'd14986ccb2dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 related_subtask_id 三列，不做历史回填。"""
    # --- update_submissions ---
    with op.batch_alter_table('update_submissions', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('related_subtask_id', sa.Integer(), nullable=True)
        )
        batch_op.create_index(
            'ix_update_submissions_related_subtask_id',
            ['related_subtask_id'],
            unique=False,
        )
        batch_op.create_foreign_key(
            'fk_upd_sub_related_subtask_id_subtasks',
            'subtasks',
            ['related_subtask_id'],
            ['id'],
        )

    # --- achievements ---
    with op.batch_alter_table('achievements', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('related_subtask_id', sa.Integer(), nullable=True)
        )
        batch_op.create_index(
            'ix_achievements_related_subtask_id',
            ['related_subtask_id'],
            unique=False,
        )
        batch_op.create_foreign_key(
            'fk_achievements_related_subtask_id_subtasks',
            'subtasks',
            ['related_subtask_id'],
            ['id'],
        )

    # --- issues ---
    with op.batch_alter_table('issues', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('related_subtask_id', sa.Integer(), nullable=True)
        )
        batch_op.create_index(
            'ix_issues_related_subtask_id',
            ['related_subtask_id'],
            unique=False,
        )
        batch_op.create_foreign_key(
            'fk_issues_related_subtask_id_subtasks',
            'subtasks',
            ['related_subtask_id'],
            ['id'],
        )

    # 不做历史数据回填 UPDATE


def downgrade() -> None:
    """删除 related_subtask_id 三列。"""
    # --- issues ---
    with op.batch_alter_table('issues', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_issues_related_subtask_id_subtasks',
            type_='foreignkey',
        )
        batch_op.drop_index('ix_issues_related_subtask_id')
        batch_op.drop_column('related_subtask_id')

    # --- achievements ---
    with op.batch_alter_table('achievements', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_achievements_related_subtask_id_subtasks',
            type_='foreignkey',
        )
        batch_op.drop_index('ix_achievements_related_subtask_id')
        batch_op.drop_column('related_subtask_id')

    # --- update_submissions ---
    with op.batch_alter_table('update_submissions', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_upd_sub_related_subtask_id_subtasks',
            type_='foreignkey',
        )
        batch_op.drop_index('ix_update_submissions_related_subtask_id')
        batch_op.drop_column('related_subtask_id')
