# PostgreSQL retry-link migration gate repair

## Goal

Restore the production runtime gate by making the existing retry-link migration
upgrade cleanly on both SQLite and PostgreSQL, without changing the
`ProjectInitAnalysisRun` data model or retry semantics.

## Cause

Migration `d4e5f6a7b8c9` recreates `project_init_analysis_runs` while adding a
self-referencing foreign key. PostgreSQL rejects the temporary replacement
table because the self-reference is created before the replacement table has a
usable unique key.

## Design

Keep the `retry_of_run_id` nullable column, its self-reference, and its unique
index. On PostgreSQL, add the column to the existing table and create the
foreign key separately, so the referenced primary key already exists. Keep a
SQLite-compatible batch path because SQLite cannot add a foreign-key constraint
through ordinary `ALTER TABLE` operations.

The migration must remain idempotent within Alembic's revision history: it is
only executed once per database, and databases that have already recorded this
revision are not rewritten.

## Verification

1. Add a PostgreSQL migration regression test that upgrades through this
   revision and asserts the retry-link column, foreign key, and unique index.
2. Run that test before the production change and observe the current
   PostgreSQL failure.
3. Run the focused migration tests after the change.
4. Run the full backend suite and the production-runtime workflow-equivalent
   checks to identify and fix any remaining independent failures.

## Scope

This repair is limited to the migration and its tests. Product behavior,
existing retry data, and unrelated frontend test expectations are unchanged
unless the subsequent full-suite run proves a separate regression.
