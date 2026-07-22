"""add cross-project update submission batches

Revision ID: e2b7c4d9a610
Revises: c8e4f2a7d901
"""

from alembic import op
import sqlalchemy as sa


revision = "e2b7c4d9a610"
down_revision = "c8e4f2a7d901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "update_submission_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_request_id", sa.String(length=64), nullable=False),
        sa.Column("submitter", sa.String(length=50), nullable=True),
        sa.Column("submitter_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("submission_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_update_submission_batches_id", "update_submission_batches", ["id"])
    op.create_index(
        "ix_update_submission_batches_client_request_id",
        "update_submission_batches", ["client_request_id"], unique=True,
    )
    op.create_index(
        "ix_update_submission_batches_submitter_id",
        "update_submission_batches", ["submitter_id"],
    )
    op.create_index(
        "ix_update_submission_batches_source_type",
        "update_submission_batches", ["source_type"],
    )
    with op.batch_alter_table("update_submissions") as batch_op:
        batch_op.add_column(sa.Column("batch_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("batch_order", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_update_submissions_batch_id", "update_submission_batches", ["batch_id"], ["id"]
        )
        batch_op.create_index("ix_update_submissions_batch_id", ["batch_id"])


def downgrade() -> None:
    with op.batch_alter_table("update_submissions") as batch_op:
        batch_op.drop_index("ix_update_submissions_batch_id")
        batch_op.drop_constraint("fk_update_submissions_batch_id", type_="foreignkey")
        batch_op.drop_column("batch_order")
        batch_op.drop_column("batch_id")
    op.drop_index("ix_update_submission_batches_source_type", table_name="update_submission_batches")
    op.drop_index("ix_update_submission_batches_submitter_id", table_name="update_submission_batches")
    op.drop_index("ix_update_submission_batches_client_request_id", table_name="update_submission_batches")
    op.drop_index("ix_update_submission_batches_id", table_name="update_submission_batches")
    op.drop_table("update_submission_batches")
