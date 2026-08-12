"""add meeting location and copied-to metadata

Revision ID: f2a3b4c5d6e7
Revises: e5f6a7b8c9d0
"""

from alembic import op
import sqlalchemy as sa


revision = "f2a3b4c5d6e7"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("meetings", "meeting_revisions"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("location", sa.String(length=200), nullable=False, server_default=""))
            batch_op.add_column(sa.Column("copied_to", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    for table_name in ("meeting_revisions", "meetings"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("copied_to")
            batch_op.drop_column("location")
