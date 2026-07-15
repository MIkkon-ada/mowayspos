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

The current migration chain cannot bootstrap a completely empty database because its
initial revision assumes pre-existing tables. That is the separate
`DB-SAFETY-P0-B-MIGRATION-BOOTSTRAP` task; this gate does not conceal or repair it.
P4-P1 remains frozen until the safety work and migration bootstrap are reviewed.
