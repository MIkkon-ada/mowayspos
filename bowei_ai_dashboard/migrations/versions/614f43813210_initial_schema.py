"""initial_schema — baseline

这是 Alembic 接入时的基准版本，不执行任何 DDL。
现有数据库（SQLite）已有完整 schema，通过 `alembic stamp head` 标记为此版本即可。
新数据库（如 PostgreSQL）由 main.py 的 Base.metadata.create_all() 建表，
然后同样 `alembic stamp head` 标记基准。

后续每次 schema 变更生成新的 revision，走正常 upgrade 流程。

Revision ID: 614f43813210
Revises:
Create Date: 2026-06-23 11:10:45.034784

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '614f43813210'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass  # baseline: DB schema already matches models at this point


def downgrade() -> None:
    pass  # baseline: nothing to revert
