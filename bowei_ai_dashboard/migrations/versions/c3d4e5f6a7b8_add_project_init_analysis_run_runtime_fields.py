"""add project init analysis snapshot and runtime timestamps

Revision ID: c3d4e5f6a7b8
Revises: b8d1e4c6a739
"""

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b8d1e4c6a739"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_init_analysis_runs", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("snapshot_json", sa.Text(), nullable=False, server_default="{}")
        )
        batch_op.alter_column("snapshot_json", server_default=None)
        batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("finished_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_init_analysis_runs", "finished_at")
    op.drop_column("project_init_analysis_runs", "started_at")
    op.drop_column("project_init_analysis_runs", "snapshot_json")
