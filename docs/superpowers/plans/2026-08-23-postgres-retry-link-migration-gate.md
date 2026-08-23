# PostgreSQL Retry-Link Migration Gate Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the project-init retry-link migration upgrade successfully on a fresh PostgreSQL database and restore the runtime gate's migration foundation.

**Architecture:** Keep the existing nullable `retry_of_run_id`, self-referencing foreign key, and unique index. Use ordinary PostgreSQL `ALTER TABLE` operations so the referenced primary key exists before the foreign key is added; retain Alembic batch recreation for SQLite. A dedicated PostgreSQL upgrade regression test creates a fresh database without the failing `postgres_database` fixture.

**Tech Stack:** Alembic, SQLAlchemy, PostgreSQL via psycopg, SQLite, pytest.

---

## File map

- Modify: `bowei_ai_dashboard/migrations/versions/d4e5f6a7b8c9_add_project_init_retry_link.py`
  - Make the self-reference migration dialect-safe for PostgreSQL and SQLite.
- Modify: `bowei_ai_dashboard/tests/test_sqlite_to_postgres_migration.py`
  - Add a focused fresh-PostgreSQL upgrade regression test and schema assertions.

### Task 1: Reproduce the PostgreSQL migration failure

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_sqlite_to_postgres_migration.py`

- [ ] **Step 1: Write a focused failing PostgreSQL upgrade test**

Add this helper and test after the existing `postgres_database` fixture. It intentionally uses `postgres_server`, not `postgres_database`, because that fixture already runs the failing upgrade during setup.

```python
def _fresh_postgres_url(postgres_server: dict[str, object], prefix: str) -> tuple[str, str]:
    database = f"{prefix}_{uuid.uuid4().hex}"
    with psycopg.connect(postgres_server["admin_url"], autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    url = (
        f"postgresql+psycopg://moways_migration:{postgres_server['password']}"
        f"@127.0.0.1:{postgres_server['port']}/{database}"
    )
    return database, url


def test_retry_link_migration_upgrades_on_fresh_postgresql(postgres_server):
    database, database_url = _fresh_postgres_url(postgres_server, "retry_link")
    try:
        result = _run_alembic(database_url, "upgrade", "head")
        assert result.returncode == 0, _output(result)
        with psycopg.connect(_psycopg_url(database_url)) as connection:
            columns = {
                row[0]
                for row in connection.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='project_init_analysis_runs'"
                )
            }
            assert "retry_of_run_id" in columns
            constraints = {
                row[0]
                for row in connection.execute(
                    "SELECT constraint_name FROM information_schema.table_constraints "
                    "WHERE table_schema='public' AND table_name='project_init_analysis_runs'"
                )
            }
            assert "fk_project_init_analysis_retry_of" in constraints
    finally:
        with psycopg.connect(postgres_server["admin_url"], autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))
```

- [ ] **Step 2: Run the test and verify the expected RED failure**

Run:

```powershell
cd bowei_ai_dashboard
..\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest tests/test_sqlite_to_postgres_migration.py::test_retry_link_migration_upgrades_on_fresh_postgresql -q
```

Expected: the assertion fails because Alembic's PostgreSQL upgrade reports `InvalidForeignKey` while recreating `project_init_analysis_runs`.

### Task 2: Make the migration dialect-safe

**Files:**
- Modify: `bowei_ai_dashboard/migrations/versions/d4e5f6a7b8c9_add_project_init_retry_link.py`

- [ ] **Step 1: Replace PostgreSQL batch recreation with ordered ALTER operations**

Implement these helpers and use them from `upgrade()` and `downgrade()`:

```python
def _retry_column() -> sa.Column:
    return sa.Column("retry_of_run_id", sa.Integer(), nullable=True)


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("project_init_analysis_runs", recreate="always") as batch_op:
            batch_op.add_column(_retry_column())
            batch_op.create_foreign_key(
                "fk_project_init_analysis_retry_of",
                "project_init_analysis_runs",
                ["retry_of_run_id"],
                ["id"],
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
```

For `downgrade()`, drop the unique index first. On SQLite use `batch_op.drop_constraint(..., type_="foreignkey")` followed by `batch_op.drop_column("retry_of_run_id")`; on PostgreSQL use `op.drop_constraint(..., "project_init_analysis_runs", type_="foreignkey")` followed by `op.drop_column(...)`.

- [ ] **Step 2: Run the focused regression test and verify GREEN**

Run:

```powershell
cd bowei_ai_dashboard
..\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest tests/test_sqlite_to_postgres_migration.py::test_retry_link_migration_upgrades_on_fresh_postgresql -q
```

Expected: `1 passed` and the test confirms the column and named self-reference exist.

- [ ] **Step 3: Run cross-dialect migration coverage**

Run:

```powershell
cd bowei_ai_dashboard
..\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest tests/test_sqlite_to_postgres_migration.py -q
```

Expected: all migration tests pass on SQLite and PostgreSQL.

- [ ] **Step 4: Commit the regression and migration repair**

```powershell
git add bowei_ai_dashboard/migrations/versions/d4e5f6a7b8c9_add_project_init_retry_link.py bowei_ai_dashboard/tests/test_sqlite_to_postgres_migration.py
git commit -m "fix: support retry link migration on postgres"
```

### Task 3: Re-establish the production gate baseline

**Files:**
- No production-file change unless the full suite reports a failure independent of the repaired migration.

- [ ] **Step 1: Run the full backend suite**

Run:

```powershell
cd bowei_ai_dashboard
..\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest tests -q --tb=no
```

Expected: the migration bootstrap errors are gone. If another failure remains, record its exact test name and traceback; do not broaden this migration repair without a separate diagnosis and plan.

- [ ] **Step 2: Run the frontend production build**

Run:

```powershell
cd frontend
npm run build
```

Expected: TypeScript and Vite complete with exit code 0.
