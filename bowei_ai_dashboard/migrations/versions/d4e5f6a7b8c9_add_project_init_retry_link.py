"""add immutable retry link for project-init analysis runs

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def _retry_column() -> sa.Column:
    return sa.Column("retry_of_run_id", sa.Integer(), nullable=True)


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("project_init_analysis_runs", recreate="always") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "retry_of_run_id",
                    sa.Integer(),
                    sa.ForeignKey("project_init_analysis_runs.id", name="fk_project_init_analysis_retry_of"),
                    nullable=True,
                )
            )
    else:
        op.add_column("project_init_analysis_runs", _retry_column())
        op.create_foreign_key(
            "fk_project_init_analysis_retry_of",
            "project_init_analysis_runs",
            "project_init_analysis_runs",
            ["retry_of_run_id"],
            ["id"],
        )
    op.create_index(
        "uq_project_init_analysis_runs_retry_of",
        "project_init_analysis_runs",
        ["retry_of_run_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_project_init_analysis_runs_retry_of", table_name="project_init_analysis_runs")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("project_init_analysis_runs", recreate="always") as batch_op:
            batch_op.drop_column("retry_of_run_id")
    else:
        op.drop_constraint(
            "fk_project_init_analysis_retry_of",
            "project_init_analysis_runs",
            type_="foreignkey",
        )
        op.drop_column("project_init_analysis_runs", "retry_of_run_id")
