"""Safely restore optional execution-schedule tables on an explicitly approved target."""

import sys
from pathlib import Path

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database_safety import (
    authorize_protected_migration,
    normalize_database_target,
    print_database_target,
    require_database_url,
)


database_url = require_database_url()
target = normalize_database_target(database_url)
print_database_target(database_url, mode="online")
authorize_protected_migration(database_url)

from app.services.execution_schedule_schema import reconcile_execution_schedule_schema


engine = create_engine(target.engine_url)
with engine.begin() as connection:
    result = reconcile_execution_schedule_schema(connection)

print(f"execution schedule schema: {result}")
