# Task-plan Timeline and Date Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show one AI-plan batch event in the key-task timeline and show each task plan's status from its planned dates without changing stored manual statuses.

**Architecture:** Aggregate legacy per-plan AI creation events only in the timeline response, while future confirmations create one run-level event. Reuse the monthly-plan display-status projection in the workspace so date-based labels are consistent across views.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React, TypeScript, Vitest.

---

### Task 1: Aggregate AI plan creation events

**Files:**
- Modify: `bowei_ai_dashboard/app/services/task_plan_proposals.py`
- Modify: `bowei_ai_dashboard/app/services/key_task_execution.py`
- Test: `bowei_ai_dashboard/tests/test_task_plan_proposals.py`

- [ ] Write a failing pytest case proving a two-plan AI confirmation emits one `task_plan_proposal` timeline event with a count summary.
- [ ] Run the focused pytest case and confirm it fails because current code emits one event per plan.
- [ ] Create one run-level event after all plans have been created; aggregate legacy same-minute events in the timeline response.
- [ ] Run focused backend tests and confirm they pass.

### Task 2: Display date-derived status in the workspace

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/monthly_plans.py`
- Modify: `bowei_ai_dashboard/app/services/key_task_execution.py`
- Modify: `frontend/src/api/keyTaskWorkspace.ts`
- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanTable.tsx`
- Test: `bowei_ai_dashboard/tests/test_key_task_execution_workspace.py`
- Test: `frontend/src/components/key-task-workspace/ExecutionPlanTable.test.tsx`

- [ ] Write failing backend and UI tests for future, active, and overdue plan display states.
- [ ] Run focused tests and confirm they fail because the workspace uses the stored status.
- [ ] Keep completed, cancelled, and paused plans unchanged; derive `未开始`, `进行中`, or `已延期` only for dated active plans, and return the matching summary count.
- [ ] Run focused backend and frontend tests, then build the frontend.
