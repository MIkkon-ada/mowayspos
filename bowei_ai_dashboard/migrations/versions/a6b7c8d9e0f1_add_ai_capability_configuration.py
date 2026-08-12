"""add AI capability configuration tables

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
"""

from alembic import op
import sqlalchemy as sa


revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=96), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("model_type", sa.String(length=24), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(length=24), nullable=False, server_default="custom"),
        sa.Column("managed_by", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_ai_models_code"),
    )
    for column in ("id", "code", "provider", "model_type", "enabled", "source"):
        op.create_index(f"ix_ai_models_{column}", "ai_models", [column])

    op.create_table(
        "ai_model_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("encrypted_app_secret", sa.Text(), nullable=False, server_default=""),
        sa.Column("key_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["model_id"], ["ai_models.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", name="uq_ai_model_credentials_model"),
    )
    for column in ("id", "model_id"):
        op.create_index(
            f"ix_ai_model_credentials_{column}", "ai_model_credentials", [column]
        )

    op.create_table(
        "ai_capability_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("capability_key", sa.String(length=96), nullable=False),
        sa.Column("primary_model_id", sa.Integer(), nullable=True),
        sa.Column("fallback_model_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["primary_model_id"], ["ai_models.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("capability_key", name="uq_ai_capability_policies_key"),
    )
    for column in ("id", "capability_key", "primary_model_id", "enabled"):
        op.create_index(
            f"ix_ai_capability_policies_{column}", "ai_capability_policies", [column]
        )

    op.create_table(
        "ai_invocation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("capability_key", sa.String(length=96), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("model_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("resource_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("actor", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["model_id"], ["ai_models.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "id",
        "capability_key",
        "model_id",
        "status",
        "error_code",
        "resource_type",
        "resource_id",
        "actor",
    ):
        op.create_index(f"ix_ai_invocation_logs_{column}", "ai_invocation_logs", [column])


def downgrade() -> None:
    for column in (
        "actor",
        "resource_id",
        "resource_type",
        "error_code",
        "status",
        "model_id",
        "capability_key",
        "id",
    ):
        op.drop_index(f"ix_ai_invocation_logs_{column}", table_name="ai_invocation_logs")
    op.drop_table("ai_invocation_logs")

    for column in ("enabled", "primary_model_id", "capability_key", "id"):
        op.drop_index(
            f"ix_ai_capability_policies_{column}", table_name="ai_capability_policies"
        )
    op.drop_table("ai_capability_policies")

    for column in ("model_id", "id"):
        op.drop_index(
            f"ix_ai_model_credentials_{column}", table_name="ai_model_credentials"
        )
    op.drop_table("ai_model_credentials")

    for column in ("source", "enabled", "model_type", "provider", "code", "id"):
        op.drop_index(f"ix_ai_models_{column}", table_name="ai_models")
    op.drop_table("ai_models")
