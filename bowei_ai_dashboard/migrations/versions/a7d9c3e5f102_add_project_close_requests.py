"""add project close requests

Revision ID: a7d9c3e5f102
Revises: 4bf512ac2391
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7d9c3e5f102"
down_revision: Union[str, Sequence[str], None] = "4bf512ac2391"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_close_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requester_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("objective_result", sa.Text(), nullable=False),
        sa.Column("unfinished_items_json", sa.Text(), nullable=False),
        sa.Column("remaining_risks_json", sa.Text(), nullable=False),
        sa.Column("handover_plan", sa.Text(), nullable=False),
        sa.Column("retrospective", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reviewer_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_project_close_requests_id", "project_close_requests", ["id"])
    op.create_index("ix_project_close_requests_project_id", "project_close_requests", ["project_id"])
    op.create_index(
        "ix_project_close_requests_requester_person_id",
        "project_close_requests",
        ["requester_person_id"],
    )
    op.create_index(
        "ix_project_close_requests_reviewer_person_id",
        "project_close_requests",
        ["reviewer_person_id"],
    )
    op.create_index("ix_project_close_requests_status", "project_close_requests", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM project_close_requests LIMIT 1")).first():
        raise RuntimeError("project_close_requests contains data")
    if bind.execute(
        sa.text("SELECT 1 FROM projects WHERE status IN ('pending_close', 'ended') LIMIT 1")
    ).first():
        raise RuntimeError("projects still use pending_close or ended")

    op.drop_index("ix_project_close_requests_status", table_name="project_close_requests")
    op.drop_index("ix_project_close_requests_reviewer_person_id", table_name="project_close_requests")
    op.drop_index("ix_project_close_requests_requester_person_id", table_name="project_close_requests")
    op.drop_index("ix_project_close_requests_project_id", table_name="project_close_requests")
    op.drop_index("ix_project_close_requests_id", table_name="project_close_requests")
    op.drop_table("project_close_requests")
