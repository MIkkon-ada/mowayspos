# Project initiation continuity implementation plan

> Execute inline in the existing linked worktree. No subagents, deployment, mixed-worktree commit, or production database changes.

**Goal:** Make the local V2 initiation flow continuous from project draft through owner planning, return, resubmission and approval.

**Architecture:** Store per-actor owner plan drafts separately from business tasks on the project, behind project-role and lifecycle authorization. Restore saved drafts or the existing submitted plan; update existing plan rows by stable IDs. Retain the project lifecycle and AI review boundary. Use one readable project/plan structure in edit and approval views, with explicit loading, error and saved states.

**Tech Stack:** React/TypeScript, FastAPI/Pydantic, SQLAlchemy/Alembic, Vitest/pytest, browser verification.

## 1. Persistence and revision safety
- [x] Write failing backend tests for incomplete drafts, actor isolation, frozen states, return comments, stable-ID rename/removal, cross-project IDs and complete resubmission.
- [x] Add nullable/private project JSON draft storage and safe migration. GET/PUT `/api/projects/{id}/owner-plan-draft` authorize owner planning and persist no formal business rows.
- [x] Return saved partial payload plus the existing submitted plan and latest return comment. Formal submission uses stable IDs and reconciles removed rows only in editable initiation states, rejecting rows with execution history.
- [x] Clear all owner drafts after successful submission so a later return restores the reviewed plan.
- [x] Run `python -m pytest tests/test_owner_plan_draft.py tests/test_project_init_work_progress_draft.py tests/test_project_lifecycle_simplification.py` in `bowei_ai_dashboard`.

## 2. Continuous V2 editing and coherent views
- [x] Write failing interaction tests for restore/save, load failure, date typing, returned plan and full-plan preview.
- [x] Add typed draft API and restore/save lifecycle; guard leave with unsaved changes. Save incomplete fields without trimming them away; allow retries without implying submission succeeded.
- [x] Replace immediate time-range parsing with independent date fields. Keep overview compact, provide full-plan preview, use common plan presentation for preview and approval.
- [x] Change project creation wording to “保存项目草稿”, show the next step, and make approval-load failure explicit with retry and disabled approval.
- [x] Run focused Vitest tests, then `npm run test:all` and `npm run test:bundle` in `frontend-v2`.

## 3. End-to-end verification and delivery
- [x] Run backend regression and migration checks in isolated databases; never migrate an unverified live database.
- [x] Verify create/dispatch, partial save/reopen, complete submit, coach return, original-plan restore, renamed task resubmit, approval and final task consistency.
- [x] Inspect the V2 browser at desktop and compact widths; save result screenshots. Record exact passing checks and any remaining environment limitation.

Accepted scope: the user's “去帮我完善吧” approves the three goals proposed in this chat: uninterrupted editing, coherent plan views and explicit step results. Existing AI functionality is preserved; this task does not alter the core lifecycle or add a new workflow stage.

Completion evidence: docs/acceptance/2026-10-12-project-initiation-continuity.md. Backend: 2080 passed, 12 skipped. V2: 170 unit and 523 contract tests passed; production build and bundle budgets passed. Browser smoke covered the complete local initiation chain and confirmed original row identities after rename. PostgreSQL and production remain outside this local verification.
