"""Legacy initial-schema marker.

This revision is no longer the migration root. Empty databases are created
by the preceding static bootstrap revision. Databases already stamped at
614f43813210 or a later revision do not execute that predecessor again.

This revision intentionally remains free of DDL.

Revision ID: 614f43813210
Revises: 7f3a2c9d8e41
Create Date: 2026-06-23 11:10:45.034784

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '614f43813210'
down_revision: Union[str, Sequence[str], None] = '7f3a2c9d8e41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass  # baseline: DB schema already matches models at this point


def downgrade() -> None:
    pass  # baseline: nothing to revert
