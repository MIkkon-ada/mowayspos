# Database safety gate

## Why this gate exists

The application previously treated a missing `DATABASE_URL` as permission to use the
repository database and ran `create_all()` during every startup. Test, application,
and Alembic entry points could therefore select and mutate protected data without an
explicit target decision. The protected logical baseline created after the incident is:

`A2307DC2F35A4FB0468AAF756B204DE9A7329F469A27822F895454A3135D9642`

## Required target configuration

`DATABASE_URL` is mandatory. Empty, whitespace, placeholder, relative SQLite, and
unrecognized targets fail before an engine or connection is created. SQLite targets
must resolve to a canonical absolute path. Tests must use a database under the system
TEMP directory and must list every repository or formal database in
`PROTECTED_DATABASE_PATHS`.

The application rejects protected targets whenever `APP_ENV=test`. Target descriptions
contain only a canonical SQLite path or a network host/database pair; credentials are
never logged.

## Alembic

Alembic prints the sanitized target and online/offline mode before creating its
connectable. Protected migrations are rejected by default. Outside `APP_ENV=test`, a
protected migration requires the exact one-time acknowledgement:

```text
ALLOW_PROTECTED_DATABASE_MIGRATION=I_UNDERSTAND_THIS_CHANGES_PROTECTED_DATA
```

Values such as `true`, `1`, or `yes` do not authorize a migration. A verified,
separate backup and human approval are required before setting the acknowledgement.
Tests can never migrate a protected database, even with the exact value.

### Empty-database bootstrap

Revision `7f3a2c9d8e41` is the controlled Alembic root for empty databases. It
contains static DDL for the 18-table post-`d14986ccb2dd`, pre-`4bf512ac2391`
schema proven by `bowei_ai_dashboard/app/models.py` at Git commit
`d5b89b874c3547caf13eed80cff47541d38f1fbc`. The migration does not import
application models, call `Base.metadata.create_all()`, seed data, or stamp a
revision manually.

The empty-database path is:

```text
7f3a2c9d8e41 bootstrap
→ 614f43813210 legacy marker
→ d14986ccb2dd consumes bootstrap marker
→ 4bf512ac2391 adds related_subtask_id fields
```

After all baseline tables and indexes are created, the root writes exactly one
technical marker row to `_moways_migration_bootstrap` with token
`POST_D149_PRE_4BF_BOOTSTRAP_V1`. Revision `d14986ccb2dd` validates the marker
table layout, unique constraint, row count, id, and exact token before deleting
the marker and skipping only its already-satisfied schema transformation. A
malformed marker fails closed and remains available for diagnosis.

A database already stamped at `614f43813210` has no marker and therefore runs
the original `d14986ccb2dd` legacy DDL. A database already at
`4bf512ac2391` is at head and runs no ancestor revision again. No path guesses
from business-table or column existence.

Downgrade from `4bf512ac2391` to `d14986ccb2dd` remains supported. Downgrade
below `d14986ccb2dd` fails before DDL because the pre-d149 schema cannot be
reconstructed safely.

SQLite verification covers empty upgrade to d149/head, full schema comparison
with current ORM output, marker corruption, the marker-free legacy path,
current-head no-op behavior, the downgrade boundary, and default application
startup. PostgreSQL DDL compiles with the PostgreSQL dialect. PostgreSQL runtime
bootstrap is not yet verified because the local Docker daemon was unavailable;
a fresh PostgreSQL 16 database remains a mandatory deployment gate. The formal
database did not participate in bootstrap tests.

## Startup schema and development seed

Startup no longer creates or repairs schema by default. It performs a read-only schema
readiness check and instructs operators to run the approved migration procedure when
core tables are absent. Temporary development/test schema creation requires an
unprotected target plus the exact acknowledgement:

```text
ALLOW_DEV_SCHEMA_CREATE_ALL=I_UNDERSTAND_THIS_IS_DEV_ONLY
```

It is forbidden in production and on protected targets. `BOWEI_DEV_MODE=true` does not
bypass the gate: automatic seed is permitted only in development against an explicit,
unprotected database.

SQLite foreign-key enforcement is not enabled by this change because the existing data
and regression suite have not yet been qualified for that behavioral change.

## Remaining blockers

P4-P1 remains frozen until the bootstrap change is reviewed and merged. Before a
PostgreSQL deployment, run `alembic upgrade head` against a new temporary
PostgreSQL 16 database and verify the resulting schema; never reuse an existing
container, volume, or protected database for that gate.
