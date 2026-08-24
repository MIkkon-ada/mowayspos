# Resolve Alembic Migration Heads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a single Alembic migration head and schema parity so fresh database upgrades and migration tests succeed.

**Architecture:** The current key-task migration must extend the existing merge migration rather than independently merge the same two parent revisions. A follow-up compatibility migration removes three redundant primary-key indexes that a historical project-meeting migration created but the ORM does not define.

**Tech Stack:** Python, Alembic, pytest.

---

### Task 1: Link the migration chain

**Files:**
- Modify: `bowei_ai_dashboard/migrations/versions/f8a9b0c1d2e3_add_subtask_risk_fields.py:13`
- Test: `bowei_ai_dashboard/tests/test_migration_graph.py:8-18`

- [ ] **Step 1: Run the existing failing single-head regression test**

Run: `py -m pytest tests/test_migration_graph.py::test_repository_has_a_single_alembic_head -q`

Expected: FAIL because both `f8a9b0c1d2e3` and `g8h9i0j1k2l` are heads.

- [ ] **Step 2: Make the key-task migration extend the prior merge**

```python
down_revision = "g8h9i0j1k2l"
```

Keep `revision`, `branch_labels`, and the risk-field schema operations unchanged.

- [ ] **Step 3: Verify the regression test passes**

Run: `py -m pytest tests/test_migration_graph.py::test_repository_has_a_single_alembic_head -q`

Expected: PASS.

- [ ] **Step 4: Run migration-focused coverage**

Run: `py -m pytest tests/test_migration_graph.py tests/test_migration_bootstrap.py tests/test_meeting_change_set_writeback.py tests/test_project_meeting_agent_models.py tests/test_sqlite_to_postgres_migration.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the repair**

```bash
git add bowei_ai_dashboard/migrations/versions/f8a9b0c1d2e3_add_subtask_risk_fields.py docs/superpowers/plans/2026-08-24-resolve-alembic-migration-heads.md
git commit -m "fix: reconcile alembic migration heads"
```

### Task 2: Reconcile the document-source schema

**Files:**
- Create: `bowei_ai_dashboard/migrations/versions/h9i0j1k2l3m_drop_meeting_document_source_id_index.py`
- Test: `bowei_ai_dashboard/tests/test_migration_bootstrap.py:332-366`

- [ ] **Step 1: Run the existing failing schema-parity regression test**

Run: `py -m pytest tests/test_migration_bootstrap.py::test_t3_head_schema_matches_current_orm -q`

Expected: FAIL because the migrated database has redundant `id` indexes on project-meeting tables that the ORM schema does not create.

- [ ] **Step 2: Add a reversible migration that removes the redundant indexes**

```python
revision = "h9i0j1k2l3m"
down_revision = "f8a9b0c1d2e3"

def upgrade() -> None:
    op.drop_index("ix_meeting_document_sources_id", table_name="meeting_document_sources")
    op.drop_index("ix_project_meeting_runs_id", table_name="project_meeting_runs")
    op.drop_index("ix_meeting_review_events_id", table_name="meeting_review_events")

def downgrade() -> None:
    op.create_index("ix_meeting_document_sources_id", "meeting_document_sources", ["id"])
    op.create_index("ix_project_meeting_runs_id", "project_meeting_runs", ["id"])
    op.create_index("ix_meeting_review_events_id", "meeting_review_events", ["id"])
```

- [ ] **Step 3: Verify schema parity passes**

Run: `py -m pytest tests/test_migration_bootstrap.py::test_t3_head_schema_matches_current_orm -q`

Expected: PASS.

- [ ] **Step 4: Run the complete backend regression suite**

Run: `py -m pytest -q`

Expected: PASS.

- [ ] **Step 5: Commit both migration repairs**

```bash
git add bowei_ai_dashboard/migrations/versions/f8a9b0c1d2e3_add_subtask_risk_fields.py bowei_ai_dashboard/migrations/versions/h9i0j1k2l3m_drop_meeting_document_source_id_index.py docs/superpowers/plans/2026-08-24-resolve-alembic-migration-heads.md
git commit -m "fix: reconcile alembic migration heads"
```
