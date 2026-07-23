# P7-P2 Cross-Project Submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Atomically submit a reviewed cross-project work report as one batch with one existing `UpdateSubmission` per project, while preserving the legacy single-task submission and all existing review handlers.

**Architecture:** Add a small batch aggregate table plus nullable batch linkage on existing submissions. A dedicated service validates every reviewed task card from database ownership, groups cards by project, and creates the batch, project submissions, and notifications in one transaction. The frontend uses the batch endpoint only for all-work and project scopes, then groups personal history by batch.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, React, TypeScript, Node test runner, pytest.

**Execution constraint:** Do not commit, push, or create a PR.

---

### Task 1: Batch persistence and migration

**Files:**
- Modify: `bowei_ai_dashboard/app/models.py`
- Create: `bowei_ai_dashboard/migrations/versions/e2b7c4d9a610_add_update_submission_batches.py`
- Create: `bowei_ai_dashboard/tests/test_cross_project_submission_batch_migration.py`

- [ ] Write migration tests asserting the new table, unique request ID, nullable `batch_id`, stable order column, foreign key, and upgrade/downgrade/upgrade safety.
- [ ] Run the migration test and verify it fails because the revision and ORM model do not exist.
- [ ] Add `UpdateSubmissionBatch`, `UpdateSubmission.batch_id`, and `UpdateSubmission.batch_order`.
- [ ] Add an Alembic revision after the current head with SQLite/PostgreSQL-compatible upgrade and downgrade operations.
- [ ] Run the migration test and existing migration bootstrap tests until green.

### Task 2: Batch request/response contract and atomic service

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Create: `bowei_ai_dashboard/app/services/cross_project_submission.py`
- Create: `bowei_ai_dashboard/tests/test_cross_project_submission_batch.py`

- [ ] Write failing tests for two-project splitting, same-project card grouping, project-scoped card payloads, invalid ownership zero-write behavior, unauthorized/archived project rollback, and idempotent replay.
- [ ] Run the new test module and confirm failures are caused by the missing schema and service.
- [ ] Define `BatchUpdateRequest` with bounded `client_request_id`, source, title, transcript, and `human_result`.
- [ ] Implement card identity validation by loading `Task` and `SubTask`, checking their relationship, deriving project ID from the database, and rejecting unresolved cards with their source index.
- [ ] Implement project permission and lifecycle validation before any write.
- [ ] Implement stable project grouping and project-scoped copies of `human_result.task_reports`.
- [ ] Create one batch plus one submission per project and enqueue one owner notification per project without committing inside the service.
- [ ] Return the existing batch on idempotent replay and do not create notifications again.
- [ ] Run the new backend tests until green.

### Task 3: Batch endpoint and personal-history metadata

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/updates.py`
- Modify: `bowei_ai_dashboard/tests/test_cross_project_submission_batch.py`

- [ ] Add a failing endpoint test asserting `POST /api/updates/batch` commits once and returns batch plus ordered child submissions.
- [ ] Add failing history tests asserting `mine=true` returns `batch_id`, `batch_order`, project name, and batch child count without changing legacy records.
- [ ] Run the targeted tests and verify the missing route/metadata failures.
- [ ] Add the batch route using the service and one router-level commit/rollback boundary.
- [ ] Extend personal-history serialization with batch metadata and resolved project name.
- [ ] Run batch tests plus existing update submission and confirmation tests.

### Task 4: Frontend API and scope-aware formal submission

**Files:**
- Modify: `frontend/src/api/updates.ts`
- Modify: `frontend/src/features/voice-update/useVoiceSubmission.ts`
- Modify: `frontend/src/pages/VoiceUpdatePage.tsx`
- Modify: `frontend/src/features/voice-update/VoiceUpdateSubmitPanel.tsx`
- Modify: `frontend/tests/workReportFlowPage.test.mjs`

- [ ] Add failing structure tests asserting all/project scopes call `createUpdateBatch`, task scope keeps `createUpdate`, and unresolved cards remain blocked.
- [ ] Run the work-report test and confirm the new assertions fail.
- [ ] Add typed batch request/result definitions and `createUpdateBatch()` for `/api/updates/batch`.
- [ ] Pass `reportScope` into submission state and build the final reviewed task-card payload without rebinding all cards to one selected task.
- [ ] Generate one stable request ID per submit attempt and retain it for retry after an unknown network result.
- [ ] Keep the existing submit lock, failure state preservation, task-scope `createUpdate`, and draft behavior.
- [ ] Enable formal submission for resolved all/project drafts and retain explicit disabled guidance for unresolved drafts.
- [ ] Run the work-report test until green.

### Task 5: Batch-aware personal history

**Files:**
- Modify: `frontend/src/api/updates.ts`
- Modify: `frontend/src/features/voice-update/useVoiceHistory.ts`
- Modify: `frontend/src/features/voice-update/VoiceUpdateHistoryDrawer.tsx`
- Modify: `frontend/tests/workReportFlowPage.test.mjs`

- [ ] Add failing tests for grouping equal `batch_id`, leaving legacy submissions independent, aggregate status mapping, project child rows, and opening the existing child detail.
- [ ] Run the work-report test and verify the history assertions fail.
- [ ] Add a pure history grouping function that preserves chronological order and derives display-only aggregate state through normalized child statuses.
- [ ] Render one batch parent with project count and expandable child project/status rows.
- [ ] Route child clicks into the existing history detail and resubmission flow.
- [ ] Focus the newly returned batch after a successful batch submit.
- [ ] Run the work-report test until green.

### Task 6: Compatibility, atomicity, and visual acceptance

**Files:**
- Modify tests only if a discovered regression requires a new reproducer before its fix.

- [ ] Run `python -m compileall app`.
- [ ] Run the batch, migration, update, permission, and confirmation pytest modules.
- [ ] Run migration upgrade/downgrade/upgrade against a temporary SQLite database.
- [ ] Run `npm run build`.
- [ ] Run every frontend `.mjs` test.
- [ ] Start the P7 backend and frontend with the correct database and allowed origin.
- [ ] In the real browser, submit one reviewed report spanning at least two projects; verify the response creates one batch and project-scoped children.
- [ ] Verify each project child appears only in its corresponding reviewer queue, without changing existing handlers.
- [ ] Verify personal history shows one batch with project children and independent statuses.
- [ ] Save screenshots outside the repository.
- [ ] Run `git diff --check` and report `git status` without committing.
