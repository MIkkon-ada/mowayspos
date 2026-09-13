"""Remove the unused meeting-document-source reverse link.

Revision ID: m4n5o6p7q8r
Revises: l3m4n5o6p7q
"""

from alembic import op
import sqlalchemy as sa


revision = "m4n5o6p7q8r"
down_revision = "l3m4n5o6p7q"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("meeting_document_sources", recreate="always") as batch:
            batch.drop_index("ix_meeting_document_sources_meeting_id")
            batch.drop_column("meeting_id")
        return

    op.drop_constraint(
        "meeting_document_sources_meeting_id_fkey",
        "meeting_document_sources",
        type_="foreignkey",
    )
    op.drop_index("ix_meeting_document_sources_meeting_id", table_name="meeting_document_sources")
    op.drop_column("meeting_document_sources", "meeting_id")


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("meeting_document_sources", recreate="always") as batch:
            batch.add_column(sa.Column("meeting_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_meeting_document_sources_meeting_id",
                "meetings",
                ["meeting_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_index("ix_meeting_document_sources_meeting_id", ["meeting_id"])
    else:
        op.add_column("meeting_document_sources", sa.Column("meeting_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "meeting_document_sources_meeting_id_fkey",
            "meeting_document_sources",
            "meetings",
            ["meeting_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_meeting_document_sources_meeting_id", "meeting_document_sources", ["meeting_id"])

    op.execute(
        """
        UPDATE meeting_document_sources
        SET meeting_id = (
            SELECT MIN(meetings.id)
            FROM meetings
            WHERE meetings.document_source_id = meeting_document_sources.id
        )
        WHERE EXISTS (
            SELECT 1
            FROM meetings
            WHERE meetings.document_source_id = meeting_document_sources.id
        )
        """
    )
