"""add meeting organizer

Revision ID: f4a5b6c7d8e9
Revises: f3a4b5c6d7e8
"""

from alembic import op
import sqlalchemy as sa


revision = "f4a5b6c7d8e9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("meetings", "meeting_revisions"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(sa.Column("organizer", sa.String(length=100), nullable=False, server_default=""))


def downgrade() -> None:
    for table_name in ("meeting_revisions", "meetings"):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column("organizer")
