# Meeting Document Source Foreign-Key Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Do not dispatch subagents for this repository. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除未被读取的会议文档来源反向外键，消除 ORM 循环依赖警告，同时保持会议文档业务链路兼容。

**Architecture:** `meetings.document_source_id` 保持为会议到来源的唯一关联；`meeting_document_sources.meeting_id`、对应外键和索引通过 Alembic 迁移删除。测试覆盖 metadata 排序、SQLite 升降级和 AI 草稿会议的正向关联。

**Tech Stack:** Python 3.12, SQLAlchemy, Alembic, SQLite, PostgreSQL 16, pytest

---

## Task 1: Freeze the one-way lineage contract

**Files:**

- Create: `bowei_ai_dashboard/tests/test_meeting_document_source_fk_governance.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py`

- [ ] **Step 1: Add failing metadata and lineage assertions**

Create a test that loads `Base.metadata.sorted_tables` under `warnings.catch_warnings(record=True)` and asserts no warning contains both `meeting_document_sources` and `meetings`. Assert the `meeting_document_sources` table has no `meeting_id` column while `meetings.document_source_id` remains a foreign key to `meeting_document_sources.id`.

In `test_project_meeting_agent_processing.py`, after the existing AI-draft assertions, assert that the created meeting retains `document_source_id == run.document_source_id`; remove any assertion of a reverse source link.

- [ ] **Step 2: Run the focused tests and observe the expected failure**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_meeting_document_source_fk_governance.py tests/test_project_meeting_agent_processing.py -q
```

Expected: the metadata assertion fails because `MeetingDocumentSource.meeting_id` still creates the cycle.

## Task 2: Remove the redundant model and write path

**Files:**

- Modify: `bowei_ai_dashboard/app/models.py`
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent_processing.py`

- [ ] **Step 1: Remove only the unused inverse field**

Delete `MeetingDocumentSource.meeting_id` and its `ForeignKey("meetings.id", ondelete="SET NULL")` declaration. Keep `Meeting.document_source_id` unchanged.

- [ ] **Step 2: Remove the sole inverse assignment**

Delete only:

```python
if source is not None:
    source.meeting_id = meeting.id
```

Do not alter the `Meeting` creation payload, `ProjectMeetingRun`, change set, document download, export, or review-package queries.

- [ ] **Step 3: Re-run focused behavior and metadata tests**

```powershell
python -m pytest tests/test_meeting_document_source_fk_governance.py tests/test_project_meeting_agent_processing.py -q
```

Expected: PASS with no meetings/document-sources sorting warning.

- [ ] **Step 4: Commit the behavior-preserving model cleanup**

```powershell
git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/app/services/project_meeting_agent_processing.py bowei_ai_dashboard/tests/test_meeting_document_source_fk_governance.py bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py
git commit -m "refactor: remove redundant meeting document source link"
```

## Task 3: Deliver the compatible Alembic migration

**Files:**

- Create: `bowei_ai_dashboard/migrations/versions/<revision>_remove_meeting_document_source_reverse_link.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_document_source_fk_governance.py`

- [ ] **Step 1: Add a failing SQLite migration round-trip test**

Create a temporary SQLite database at the migration preceding the new revision. Upgrade to the new revision and assert `PRAGMA table_info(meeting_document_sources)` lacks `meeting_id`, then downgrade and assert the column exists again, then re-upgrade and assert `PRAGMA integrity_check` is `ok`.

- [ ] **Step 2: Run the round-trip test and verify it fails before the migration exists**

```powershell
python -m pytest tests/test_meeting_document_source_fk_governance.py -q
```

Expected: FAIL because the target revision is absent.

- [ ] **Step 3: Add dialect-safe upgrade and downgrade operations**

For SQLite, use `batch_alter_table("meeting_document_sources", recreate="always")` to drop `ix_meeting_document_sources_meeting_id`, the foreign key, and `meeting_id`.

For PostgreSQL, call `op.drop_constraint` for the foreign key, `op.drop_index("ix_meeting_document_sources_meeting_id", table_name="meeting_document_sources")`, then `op.drop_column`.

In downgrade, re-add a nullable `meeting_id` integer, create its `ON DELETE SET NULL` foreign key and index. Run a best-effort backfill from `meetings.document_source_id`, selecting the lowest meeting ID when historical rows share a source.

- [ ] **Step 4: Run migration and schema tests**

```powershell
python -m pytest tests/test_meeting_document_source_fk_governance.py tests/test_migration_bootstrap.py -q
python -m alembic heads
```

Expected: tests pass and `alembic heads` reports one head.

- [ ] **Step 5: Commit the migration**

```powershell
git add bowei_ai_dashboard/migrations/versions bowei_ai_dashboard/tests/test_meeting_document_source_fk_governance.py
git commit -m "fix: remove meeting document source foreign key cycle"
```

## Task 4: Run the full delivery gate

- [ ] **Step 1: Run backend and migration verification**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests -q
python -m alembic heads
Set-Location ..
```

Expected: full pytest exits 0 without the prior meetings/document-sources circular warning.

- [ ] **Step 2: Run frontend verification and patch hygiene**

```powershell
Set-Location frontend
npm run test:all
npm run build
Set-Location ..
git diff --check
git status --short
```

Expected: all commands exit 0; the existing ExcelJS chunk-size warning may remain.

