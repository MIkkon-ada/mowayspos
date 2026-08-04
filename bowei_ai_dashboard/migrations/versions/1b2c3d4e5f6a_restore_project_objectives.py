"""restore project objectives compatibility column

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f
"""

from alembic import op
import sqlalchemy as sa


revision = "1b2c3d4e5f6a"
down_revision = "0a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("projects")}
    if "objectives" not in columns:
        op.add_column(
            "projects",
            sa.Column("objectives", sa.Text(), nullable=True, server_default=sa.text("''")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("projects")}
    if "objectives" in columns:
        op.drop_column("projects", "objectives")
