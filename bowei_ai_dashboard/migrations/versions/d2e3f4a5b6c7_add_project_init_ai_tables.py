"""add project init AI attachment and analysis tables

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""

from alembic import op
import sqlalchemy as sa


revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_init_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.String(50), nullable=False),
        sa.Column(
            "uploaded_by_person_id",
            sa.Integer(),
            sa.ForeignKey("people.id"),
        ),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("deleted_by", sa.String(50)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index(
        "ix_project_init_attachments_id",
        "project_init_attachments",
        ["id"],
    )
    op.create_index(
        "ix_project_init_attachments_project_id",
        "project_init_attachments",
        ["project_id"],
    )
    op.create_index(
        "ix_project_init_attachments_uploaded_by",
        "project_init_attachments",
        ["uploaded_by"],
    )
    op.create_index(
        "ix_project_init_attachments_uploaded_by_person_id",
        "project_init_attachments",
        ["uploaded_by_person_id"],
    )
    op.create_index(
        "ix_project_init_attachments_deleted_at",
        "project_init_attachments",
        ["deleted_at"],
    )

    op.create_table(
        "project_init_analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("attachment_ids_json", sa.Text(), nullable=False),
        sa.Column("current_draft_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("stage", sa.String(24), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("file_results_json", sa.Text(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("created_by", sa.String(50), nullable=False),
        sa.Column(
            "created_by_person_id",
            sa.Integer(),
            sa.ForeignKey("people.id"),
        ),
        sa.Column("applied_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index(
        "ix_project_init_analysis_runs_id",
        "project_init_analysis_runs",
        ["id"],
    )
    op.create_index(
        "ix_project_init_analysis_runs_project_id",
        "project_init_analysis_runs",
        ["project_id"],
    )
    op.create_index(
        "ix_project_init_analysis_runs_status",
        "project_init_analysis_runs",
        ["status"],
    )
    op.create_index(
        "ix_project_init_analysis_runs_created_by",
        "project_init_analysis_runs",
        ["created_by"],
    )
    op.create_index(
        "ix_project_init_analysis_runs_created_by_person_id",
        "project_init_analysis_runs",
        ["created_by_person_id"],
    )


def downgrade() -> None:
    op.drop_table("project_init_analysis_runs")
    op.drop_table("project_init_attachments")
