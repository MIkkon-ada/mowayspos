"""Drop redundant project-meeting primary-key indexes.

Revision ID: h9i0j1k2l3m
Revises: f8a9b0c1d2e3
Create Date: 2026-08-24
"""

from alembic import op


revision = "h9i0j1k2l3m"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_meeting_document_sources_id", table_name="meeting_document_sources")
    op.drop_index("ix_project_meeting_runs_id", table_name="project_meeting_runs")
    op.drop_index("ix_meeting_review_events_id", table_name="meeting_review_events")


def downgrade() -> None:
    op.create_index("ix_meeting_document_sources_id", "meeting_document_sources", ["id"])
    op.create_index("ix_project_meeting_runs_id", "project_meeting_runs", ["id"])
    op.create_index("ix_meeting_review_events_id", "meeting_review_events", ["id"])
