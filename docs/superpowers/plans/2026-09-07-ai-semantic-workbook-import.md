# AI Semantic Workbook Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make project-init workbook import semantic-first so varied headers and multiline work items retain goals, acceptance criteria, process, tasks, and evidence.

**Architecture:** Keep workbook parsing lossless and AI-driven semantic normalization separate. The AI returns a canonical draft with explicit goal, acceptance criteria, process, and task fields; server-side validation preserves evidence and prevents invented people/dates. The existing owner-submit transaction remains the only writer of formal project data, with a new task process field for durable storage.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, React/TypeScript, Vitest, pytest, openpyxl.

---

### Task 1: Regression for the real workbook shape

**Files:** bowei_ai_dashboard/tests/test_project_init_ai_agent.py; bowei_ai_dashboard/tests/test_project_init_file_parser.py

- [x] Add a failing end-to-end fixture for headers 主要工作 / 目标 / 验收标准与关键成果 / 关键任务 / 推进流程, including a merged title row and multiline task cells.
- [x] Assert five parents, non-empty goal/acceptance/process, every explicit numbered task, and exact evidence ranges.
- [x] Run the focused AI and parser tests through a red-green cycle.

### Task 2: Semantic workbook normalization

**Files:** bowei_ai_dashboard/app/services/project_init_ai_agent.py; bowei_ai_dashboard/app/services/project_init_analysis.py; bowei_ai_dashboard/tests/test_project_init_ai_agent.py

- [x] Extend the validated parent draft with goal, acceptance_criteria, and process while keeping description as the legacy displayed-goal fallback.
- [x] Update the AI prompt to classify column roles by meaning, split numbered items inside multiline cells, preserve unknown columns, and emit evidence for populated fields.
- [x] Add a bounded missing-field repair pass with a reviewer warning fallback.
- [x] Run the focused AI tests and confirm the new real-header fixture passes.

### Task 3: Durable process storage and backward-compatible API

**Files:** bowei_ai_dashboard/app/models.py; bowei_ai_dashboard/migrations/versions/k2l3m4n5o6p7_add_task_plan_process.py; bowei_ai_dashboard/app/schemas.py; bowei_ai_dashboard/app/routers/projects.py; bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py

- [x] Add a failing persistence test for goal, acceptance_criteria, process, and retain the old payload path.
- [x] Add Task.plan_process as Text with an empty default and an Alembic upgrade/downgrade migration based on the current head.
- [x] Add the new draft fields to project-init and owner-submit payloads. Use description as the legacy goal fallback. Save acceptance criteria to the existing task completion-standard field and process to plan_process.
- [x] Run the focused backend tests and migration checks on a temporary database.

### Task 4: Complete preview, form, and submit flow

**Files:** frontend/src/api/projectInitAi.ts; frontend/src/api/projects.ts; frontend/src/features/settings/OwnerSubmitAiPanel.tsx; frontend/src/features/settings/OwnerSubmitModal.tsx; frontend/src/features/settings/ownerSubmitDraft.ts; related frontend tests

- [x] Add tests asserting that the owner-submit form shows goal, acceptance criteria, and process.
- [x] Decode new fields with empty-string defaults so historical runs remain readable.
- [x] Add editable goal, acceptance-criteria, and process fields while keeping existing key-task controls.
- [x] Update merge preview, applyMergedDraftToForm, current-draft snapshots, and submit conversion so the three fields survive all transitions.
- [x] Run the focused frontend tests and production build.

### Task 5: Real-file and integration verification

**Files:** existing project-init backend and frontend tests; no runtime data files

- [x] Run a read-only parser audit against bowei_ai_dashboard/data/project-init-attachments/3/1a1056680e49496da320db624d9915fc.
- [x] Run backend project-init and owner-submit suites.
- [x] Run the full frontend test suite and build.
- [x] Run git diff --check and verify the pre-existing untracked runtime data remains untouched.
- [ ] Apply the new migration to the protected local database after the approved backup/authorization procedure; the safety gate refused an unauthorized attempt.
- [ ] Commit with message feat: make project init workbook import semantic.
