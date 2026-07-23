"""add source_card_index and opinion to issues

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
"""

from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Issue 表已有 source_type / source_submission_id，只需补 2 列
    with op.batch_alter_table("issues", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_card_index", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("opinion", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("issues", schema=None) as batch_op:
        batch_op.drop_column("opinion")
        batch_op.drop_column("source_card_index")
