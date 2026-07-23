"""add wecom_userid to accounts

Revision ID: f1a2b3c4d5e6
Revises: e2b7c4d9a610
"""

from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "e2b7c4d9a610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite 不支持直接加列带索引，用 batch_alter_table 兼容
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("wecom_userid", sa.String(length=64), nullable=True))
    op.create_index("ix_accounts_wecom_userid", "accounts", ["wecom_userid"])


def downgrade() -> None:
    op.drop_index("ix_accounts_wecom_userid", table_name="accounts")
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.drop_column("wecom_userid")
