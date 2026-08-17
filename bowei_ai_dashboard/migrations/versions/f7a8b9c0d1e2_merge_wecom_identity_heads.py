"""merge the existing migration head with WeCom identity fields"""

from alembic import op  # noqa: F401


revision = "f7a8b9c0d1e2"
down_revision = ("b8c9d0e1f2a3", "f6a7b8c9d0e1")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
