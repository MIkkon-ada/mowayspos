"""Keep partial owner plans separate from business data.

Revision ID: y6z7a8b9c0d1
Revises: x5y6z7a8b9c0
"""
from alembic import op
import sqlalchemy as sa

revision = "y6z7a8b9c0d1"
down_revision = "x5y6z7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("owner_plan_drafts", sa.JSON(), nullable=False, server_default="{}"))
    for table in ["tasks", "subtasks"]:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("plan_time", existing_type=sa.String(20), type_=sa.String(80))


def downgrade():
    connection = op.get_bind()
    values = connection.execute(sa.text("SELECT owner_plan_drafts FROM projects")).scalars()
    import json
    for value in values:
        if (json.loads(value) if isinstance(value, str) else value):
            raise RuntimeError("owner plan drafts would be lost; export or submit drafts before downgrade")
    for table in ["tasks", "subtasks"]:
        if connection.execute(sa.text(f"SELECT 1 FROM {table} WHERE length(plan_time) > 20 LIMIT 1")).first():
            raise RuntimeError("owner plan dates would be truncated; export or shorten ranges before downgrade")
    for table in ["tasks", "subtasks"]:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("plan_time", existing_type=sa.String(80), type_=sa.String(20))
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("owner_plan_drafts")
