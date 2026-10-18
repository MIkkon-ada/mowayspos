"""Bind issue helpers to stable person identities.

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
"""

from alembic import op
import sqlalchemy as sa


revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("issues") as batch:
        batch.add_column(sa.Column("helper_person_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_issues_helper_person_id_people",
            "people",
            ["helper_person_id"],
            ["id"],
        )
        batch.create_index("ix_issues_helper_person_id", ["helper_person_id"])
    op.execute(
        sa.text(
            "UPDATE issues SET helper_person_id = ("
            "SELECT MIN(people.id) FROM people "
            "WHERE people.name = issues.helper AND people.is_active IS TRUE "
            "HAVING COUNT(*) = 1"
            ") WHERE helper IS NOT NULL AND TRIM(helper) <> ''"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    assigned_helpers = bind.execute(
        sa.text("SELECT 1 FROM issues WHERE helper_person_id IS NOT NULL LIMIT 1")
    ).first()
    if assigned_helpers:
        raise RuntimeError("issue helper identity data would be lost")
    with op.batch_alter_table("issues") as batch:
        batch.drop_index("ix_issues_helper_person_id")
        batch.drop_column("helper_person_id")
