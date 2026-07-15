import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make app.* importable without importing the application or its database engine.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database_safety import (  # noqa: E402
    authorize_protected_migration,
    describe_database_target,
    normalize_database_target,
    print_database_target,
    require_database_url,
)

config = context.config

_database_url = require_database_url()
_database_target = normalize_database_target(_database_url)
_migration_mode = "offline" if context.is_offline_mode() else "online"
print_database_target(_database_url, mode=_migration_mode)
if authorize_protected_migration(_database_url):
    print("WARNING: protected database migration explicitly authorized", flush=True)
    print(f"Target:\n{describe_database_target(_database_url)}", flush=True)

config.set_main_option("sqlalchemy.url", _database_target.engine_url)

# Model registration happens only after the target is validated and logged.
from app.models import Base  # noqa: E402,F401

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without opening a database connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations through a connectable created after the safety gate."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
