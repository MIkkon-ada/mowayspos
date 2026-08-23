"""Add project meeting Word sources, runs and owner review audit."""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meeting_document_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_person_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_meeting_document_sources_id", "meeting_document_sources", ["id"])
    op.create_index("ix_meeting_document_sources_project_id", "meeting_document_sources", ["project_id"])
    op.create_index("ix_meeting_document_sources_meeting_id", "meeting_document_sources", ["meeting_id"])
    op.create_index("ix_meeting_document_sources_content_hash", "meeting_document_sources", ["content_hash"])
    op.create_index("ix_meeting_document_sources_uploaded_by_person_id", "meeting_document_sources", ["uploaded_by_person_id"])

    op.create_table(
        "project_meeting_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("document_source_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("document_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="analyzing"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by_person_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_person_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["document_source_id"], ["meeting_document_sources.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_meeting_runs_id", "project_meeting_runs", ["id"])
    op.create_index("ix_project_meeting_runs_project_id", "project_meeting_runs", ["project_id"])
    op.create_index("ix_project_meeting_runs_document_source_id", "project_meeting_runs", ["document_source_id"])
    op.create_index("ix_project_meeting_runs_status", "project_meeting_runs", ["status"])
    op.create_index("ix_project_meeting_runs_created_by_person_id", "project_meeting_runs", ["created_by_person_id"])

    op.create_table(
        "meeting_review_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("actor_person_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("selected_proposal_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["actor_person_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meeting_review_events_id", "meeting_review_events", ["id"])
    op.create_index("ix_meeting_review_events_meeting_id", "meeting_review_events", ["meeting_id"])
    op.create_index("ix_meeting_review_events_action", "meeting_review_events", ["action"])
    op.create_index("ix_meeting_review_events_actor_person_id", "meeting_review_events", ["actor_person_id"])

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("meetings", recreate="always") as batch:
            batch.add_column(sa.Column("document_source_id", sa.Integer(), nullable=True))
            batch.add_column(sa.Column("review_status", sa.String(length=24), nullable=False, server_default="legacy"))
            batch.add_column(sa.Column("review_version", sa.Integer(), nullable=False, server_default="1"))
            batch.create_foreign_key("fk_meetings_document_source_id", "meeting_document_sources", ["document_source_id"], ["id"], ondelete="SET NULL")
            batch.create_index("ix_meetings_document_source_id", ["document_source_id"])
            batch.create_index("ix_meetings_review_status", ["review_status"])
    else:
        op.add_column("meetings", sa.Column("document_source_id", sa.Integer(), nullable=True))
        op.add_column("meetings", sa.Column("review_status", sa.String(length=24), nullable=False, server_default="legacy"))
        op.add_column("meetings", sa.Column("review_version", sa.Integer(), nullable=False, server_default="1"))
        op.create_foreign_key("fk_meetings_document_source_id", "meetings", "meeting_document_sources", ["document_source_id"], ["id"], ondelete="SET NULL")
        op.create_index("ix_meetings_document_source_id", "meetings", ["document_source_id"])
        op.create_index("ix_meetings_review_status", "meetings", ["review_status"])
    op.execute("UPDATE meetings SET review_status = 'legacy' WHERE review_status IS NULL OR review_status = ''")


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("meetings", recreate="always") as batch:
            batch.drop_index("ix_meetings_review_status")
            batch.drop_index("ix_meetings_document_source_id")
            batch.drop_constraint("fk_meetings_document_source_id", type_="foreignkey")
            batch.drop_column("review_version")
            batch.drop_column("review_status")
            batch.drop_column("document_source_id")
    else:
        op.drop_index("ix_meetings_review_status", table_name="meetings")
        op.drop_index("ix_meetings_document_source_id", table_name="meetings")
        op.drop_constraint("fk_meetings_document_source_id", "meetings", type_="foreignkey")
        op.drop_column("meetings", "review_version")
        op.drop_column("meetings", "review_status")
        op.drop_column("meetings", "document_source_id")

    for name in ("ix_meeting_review_events_actor_person_id", "ix_meeting_review_events_action", "ix_meeting_review_events_meeting_id", "ix_meeting_review_events_id"):
        op.drop_index(name, table_name="meeting_review_events")
    op.drop_table("meeting_review_events")
    for name in ("ix_project_meeting_runs_created_by_person_id", "ix_project_meeting_runs_status", "ix_project_meeting_runs_document_source_id", "ix_project_meeting_runs_project_id", "ix_project_meeting_runs_id"):
        op.drop_index(name, table_name="project_meeting_runs")
    op.drop_table("project_meeting_runs")
    for name in ("ix_meeting_document_sources_uploaded_by_person_id", "ix_meeting_document_sources_content_hash", "ix_meeting_document_sources_meeting_id", "ix_meeting_document_sources_project_id", "ix_meeting_document_sources_id"):
        op.drop_index(name, table_name="meeting_document_sources")
    op.drop_table("meeting_document_sources")
