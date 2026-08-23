"""Add immutable analysis lineage to meeting change proposals."""

from alembic import op
import sqlalchemy as sa


revision = "d5e6f7a8b9c0"
down_revision = "c4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("meeting_change_proposals") as batch_op:
        batch_op.add_column(
            sa.Column("lineage_json", sa.Text(), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("meeting_change_proposals") as batch_op:
        batch_op.drop_column("lineage_json")
