"""restore current project profile columns

Revision ID: c8e4f2a7d901
Revises: a7d9c3e5f102
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision = "c8e4f2a7d901"
down_revision = "a7d9c3e5f102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PROFILE_COLUMNS = (
    sa.Column("project_type", sa.Text(), nullable=True, server_default=sa.text("''")),
    sa.Column("client_name", sa.Text(), nullable=True, server_default=sa.text("''")),
    sa.Column("background", sa.Text(), nullable=True, server_default=sa.text("''")),
    sa.Column("objectives", sa.Text(), nullable=True, server_default=sa.text("''")),
    sa.Column("expected_outcomes", sa.Text(), nullable=True, server_default=sa.text("''")),
    sa.Column("lifecycle_status", sa.Text(), nullable=True, server_default=sa.text("'draft'")),
    sa.Column("kickoff_date", sa.Text(), nullable=True, server_default=sa.text("''")),
    sa.Column("kickoff_by", sa.Text(), nullable=True, server_default=sa.text("''")),
    sa.Column("initiated_by", sa.Text(), nullable=True, server_default=sa.text("''")),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("projects")}

    for column in _PROFILE_COLUMNS:
        if column.name not in existing_columns:
            op.add_column("projects", column)

    active_predicate = "is_active IS TRUE" if bind.dialect.name == "postgresql" else "is_active = 1"
    op.execute(
        sa.text(
            "UPDATE projects SET lifecycle_status = CASE "
            "WHEN status IS NOT NULL AND TRIM(status) <> '' THEN status "
            f"WHEN {active_predicate} THEN 'active' ELSE 'archived' END"
        )
    )

    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("status", server_default=sa.text("'draft'"))
        batch_op.alter_column("is_active", server_default=sa.text("false"))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("is_active", server_default=None)
        batch_op.alter_column("status", server_default=None)
    for column in reversed(_PROFILE_COLUMNS):
        op.drop_column("projects", column.name)
