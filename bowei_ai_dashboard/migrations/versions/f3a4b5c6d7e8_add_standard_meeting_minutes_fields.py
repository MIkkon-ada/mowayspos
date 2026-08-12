"""add standard meeting minutes fidelity fields

Revision ID: f3a4b5c6d7e8
Revises: f2a3b4c5d6e7
"""

from alembic import op
import sqlalchemy as sa


revision = "f3a4b5c6d7e8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("meetings", "meeting_revisions"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("agenda_items_json", sa.Text(), nullable=False, server_default="[]"))
            batch_op.add_column(sa.Column("prior_action_items_json", sa.Text(), nullable=False, server_default="[]"))
            batch_op.add_column(sa.Column("source_mode", sa.String(length=32), nullable=False, server_default="ai_analysis"))


def downgrade() -> None:
    for table_name in ("meeting_revisions", "meetings"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("source_mode")
            batch_op.drop_column("prior_action_items_json")
            batch_op.drop_column("agenda_items_json")
