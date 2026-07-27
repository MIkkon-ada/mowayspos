"""add meeting creator person id

Revision ID: b2c3d4e5f6a7
Revises: a7b8c9d0e1f2
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.add_column(sa.Column("creator_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True))
        batch_op.create_index("ix_meetings_creator_person_id", ["creator_person_id"])

def downgrade() -> None:
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.drop_index("ix_meetings_creator_person_id")
        batch_op.drop_column("creator_person_id")
