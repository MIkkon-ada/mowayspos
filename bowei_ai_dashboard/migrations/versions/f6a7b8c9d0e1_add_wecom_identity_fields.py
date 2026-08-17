"""add WeCom company identity fields to people

Revision ID: f6a7b8c9d0e1
Revises: f5a6b7c8d9e0
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.add_column(sa.Column("position_title", sa.String(length=100), nullable=True, server_default=""))
        batch_op.add_column(sa.Column("wecom_userid", sa.String(length=64), nullable=True, server_default=""))
        batch_op.add_column(sa.Column("wecom_department", sa.String(length=200), nullable=True, server_default=""))
        batch_op.add_column(sa.Column("wecom_position_title", sa.String(length=100), nullable=True, server_default=""))
        batch_op.add_column(sa.Column("department_source", sa.String(length=20), nullable=True, server_default="wecom"))
        batch_op.add_column(sa.Column("position_source", sa.String(length=20), nullable=True, server_default="wecom"))
    op.create_index("ix_people_wecom_userid", "people", ["wecom_userid"])


def downgrade() -> None:
    op.drop_index("ix_people_wecom_userid", table_name="people")
    with op.batch_alter_table("people", schema=None) as batch_op:
        batch_op.drop_column("position_source")
        batch_op.drop_column("department_source")
        batch_op.drop_column("wecom_position_title")
        batch_op.drop_column("wecom_department")
        batch_op.drop_column("wecom_userid")
        batch_op.drop_column("position_title")
