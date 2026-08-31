# AI Task Plan Proposals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate multiple auditable task-plan drafts from pasted text and meeting minutes, then require review before batch creation under key tasks.

**Architecture:** Reuse the existing meeting change-set model for document-generated `create_execution_schedule` proposals, correcting the parent-key-task persistence so existing review and post-publication writeback can execute them. Add a separate, persisted text-analysis run for a selected key task; it stores AI draft rows, their source excerpts, validation state, and reviewer edits. Both paths use one backend batch-creation service so member, status, and date rules are checked before a transaction creates any plan.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, existing AI capability service, React/TypeScript/Tailwind, Vitest, pytest.

---

### Task 1: Repair the manual plan drawer’s collaborator control

**Files:**

- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.tsx`
- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx`
- Reference: `frontend/src/components/task-management/KeyTaskSubtaskDrawer.tsx`

- [ ] **Step 1: Write failing DOM tests**

Assert that the collaborator trigger has `aria-expanded`, renders no `<select multiple>`, and that duplicate `person_id` records render only one checkbox candidate.

- [ ] **Step 2: Run the focused test**

Run: `npm run test:unit -- --run src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx`

Expected: FAIL because the drawer renders the native multiple select and does not remove duplicate members.

- [ ] **Step 3: Replace the native control**

Extract the existing compact `CollaboratorMultiSelect` behavior into a shared key-task-workspace component. It must:
- de-duplicate by `person_id`;
- exclude the selected responsible person;
- render a closed button by default and a popover of checkboxes only after click;
- retain selected IDs when the popover closes.

- [ ] **Step 4: Verify focused test**

Run the command from Step 2.

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.tsx frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx frontend/src/components/key-task-workspace/CollaboratorMultiSelect.tsx
git commit -m "fix: use compact collaborator selector for task plans"
```

### Task 2: Make meeting-created plan proposals executable

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/meetings.py:800-1108`
- Modify: `bowei_ai_dashboard/app/services/project_meeting_minutes.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_review.py`
- Modify: `frontend/src/api/meetings.ts`
- Modify: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx`

- [ ] **Step 1: Write failing backend tests**

Create a meeting result containing one `create_execution_schedule` proposal targeted at a valid key-task ID. After publish and `apply_changes`, assert:
- an `ExecutionSchedule` exists under that key task;
- its title and expected output equal the reviewed proposal;
- the `MeetingChangeProposal.parent_subtask_id` and `result_target_id` are populated;
- the proposal becomes `executed`.

Add a separate test where the proposal has no key-task target and assert it is blocked and no plan is created.

- [ ] **Step 2: Run the focused backend tests**

Run: `pytest bowei_ai_dashboard/tests/test_project_meeting_review.py -q`

Expected: the create proposal fails because `_project_meeting_change_set` currently stores the key-task ID in `parent_workstream_id` instead of `parent_subtask_id`.

- [ ] **Step 3: Correct proposal persistence and validation**

When materializing a meeting proposal:
- write `target.workstream_id` to `parent_workstream_id`;
- write `target.key_task_id` to `parent_subtask_id`;
- block `create_execution_schedule` when its key-task target, project member IDs, title, expected output, or evidence validation is invalid.

In `_execute_project_meeting_schedule_changes`, validate all selected proposals first, then create rows only after every proposal is valid. Create each row with `plan_type="month"`, the reviewed proposal fields, actor metadata, and the same execution-event source metadata used by `monthly_plans.create_monthly_plan`.

- [ ] **Step 4: Display new-plan proposals distinctly**

Extend the client type with the existing `action` field. In the review workspace, label `create_execution_schedule` as “新增任务计划建议”; show the target key task, evidence, validation state, and reviewed fields. Keep it unselectable if the target is missing or validation is not ready.

- [ ] **Step 5: Verify**

Run: `pytest bowei_ai_dashboard/tests/test_project_meeting_review.py -q` and `npm run test:unit -- --run src/features/meeting/ProjectMeetingReviewWorkspace.test.ts`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/app/services/project_meeting_minutes.py bowei_ai_dashboard/tests/test_project_meeting_review.py frontend/src/api/meetings.ts frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx frontend/src/features/meeting/ProjectMeetingReviewWorkspace.test.ts
git commit -m "feat: write reviewed meeting plan proposals"
```

### Task 3: Persist and generate text-based task-plan drafts

**Files:**

- Create: `bowei_ai_dashboard/app/services/task_plan_proposals.py`
- Create: `bowei_ai_dashboard/app/routers/task_plan_proposals.py`
- Modify: `bowei_ai_dashboard/app/models.py`
- Create: Alembic migration in `bowei_ai_dashboard/alembic/versions/`
- Modify: `bowei_ai_dashboard/app/main.py`
- Modify: `bowei_ai_dashboard/app/ai_capability_policy.py`
- Create: `bowei_ai_dashboard/tests/test_task_plan_proposals.py`

- [ ] **Step 1: Write failing service and route tests**

Use a fake AI capability response containing two proposed plans with source excerpts. Assert the create-analysis route:
- accepts a non-empty text payload for one existing, writable key task;
- persists a proposal run and two pending proposal rows;
- defaults each proposal target to the route key-task ID;
- marks a field with missing evidence as `needs_confirmation`;
- rejects callers without key-task operation permission.

- [ ] **Step 2: Run the focused test**

Run: `pytest bowei_ai_dashboard/tests/test_task_plan_proposals.py -q`

Expected: FAIL because the route, models, and AI capability are absent.

- [ ] **Step 3: Add data model and migration**

Add `TaskPlanProposalRun` with `project_id`, `key_task_id`, `source_text`, `source_hash`, `status`, `created_by_person_id`, AI audit metadata, and timestamps. Add `TaskPlanProposal` with plan field JSON, evidence JSON, validation JSON, status, reviewer edit JSON, and created-plan ID. The migration must create both tables and indexes on project/key-task/status; downgrade must drop them in reverse order.

- [ ] **Step 4: Implement AI normalization**

Add a dedicated capability key and an AI response schema limited to 20 proposals. For every proposal:
- require a non-empty title and expected output;
- resolve assignee/collaborator names only against project-member IDs;
- use the selected key task as target;
- require an exact source quote from the submitted text for every asserted field;
- set `needs_confirmation` when owner, dates, or completion definition cannot be supported by a quote.

Do not create `ExecutionSchedule` rows in this step.

- [ ] **Step 5: Commit**

```powershell
git add bowei_ai_dashboard/app/services/task_plan_proposals.py bowei_ai_dashboard/app/routers/task_plan_proposals.py bowei_ai_dashboard/app/models.py bowei_ai_dashboard/alembic/versions bowei_ai_dashboard/app/main.py bowei_ai_dashboard/app/ai_capability_policy.py bowei_ai_dashboard/tests/test_task_plan_proposals.py
git commit -m "feat: generate auditable task plan drafts from text"
```

### Task 4: Review and atomically apply selected text proposals

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/task_plan_proposals.py`
- Modify: `bowei_ai_dashboard/app/services/task_plan_proposals.py`
- Modify: `bowei_ai_dashboard/tests/test_task_plan_proposals.py`
- Modify: `frontend/src/api/keyTaskWorkspace.ts`
- Create: `frontend/src/components/key-task-workspace/TaskPlanProposalReview.tsx`
- Create: `frontend/src/components/key-task-workspace/TaskPlanProposalReview.test.tsx`

- [ ] **Step 1: Write failing batch-apply tests**

Construct three reviewed proposals, with one invalid collaborator ID. Assert the apply route returns 422 and creates zero schedules. Correct the invalid row and assert the same request creates only the selected rows, records their created IDs, and refreshes the key-task execution event projection.

- [ ] **Step 2: Run focused backend tests**

Run: `pytest bowei_ai_dashboard/tests/test_task_plan_proposals.py -q`

Expected: FAIL because no review/apply endpoint exists.

- [ ] **Step 3: Implement review and apply endpoints**

Provide:
- `GET /api/key-tasks/{key_task_id}/task-plan-proposal-runs/{run_id}`;
- `PATCH /api/task-plan-proposals/{proposal_id}` for owner edits;
- `POST /api/task-plan-proposal-runs/{run_id}/apply` with selected IDs.

The apply service must lock selected pending proposals, revalidate key-task status, people, dates, required fields, and evidence state, then create all schedules and execution events within one transaction. It must reject unselected, unmatched, or needs-confirmation proposals. Mark only successfully committed rows `executed`.

- [ ] **Step 4: Implement the review list**

The component displays editable candidate rows with source quotes, checkbox selection, status chips, and an explicit key-task selector only for document-origin proposals that are unmatched. It disables “确认创建已选计划” until every selected row is ready. On success, close the drawer and invoke the workspace refresh callback.

- [ ] **Step 5: Verify and commit**

Run: `pytest bowei_ai_dashboard/tests/test_task_plan_proposals.py -q` and `npm run test:unit -- --run src/components/key-task-workspace/TaskPlanProposalReview.test.tsx`.

```powershell
git add bowei_ai_dashboard/app/routers/task_plan_proposals.py bowei_ai_dashboard/app/services/task_plan_proposals.py bowei_ai_dashboard/tests/test_task_plan_proposals.py frontend/src/api/keyTaskWorkspace.ts frontend/src/components/key-task-workspace/TaskPlanProposalReview.tsx frontend/src/components/key-task-workspace/TaskPlanProposalReview.test.tsx
git commit -m "feat: review and batch apply AI task plan drafts"
```

### Task 5: Connect direct text entry and verify the combined workflow

**Files:**

- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.tsx`
- Modify: `frontend/src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx`
- Modify: `frontend/tests/keyTaskExecutionWorkspace.test.mjs`
- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx`

- [ ] **Step 1: Write failing UI tests**

Assert the drawer has separate “手工新增” and “AI 拆解” modes. In AI mode, entering text and clicking “生成计划草稿” calls the selected key-task analysis route and then renders `TaskPlanProposalReview`; manual mode still submits exactly one direct plan.

- [ ] **Step 2: Run focused tests**

Run: `npm run test:unit -- --run src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx src/components/key-task-workspace/TaskPlanProposalReview.test.tsx; node --test tests/keyTaskExecutionWorkspace.test.mjs`

Expected: FAIL because the drawer has only manual fields.

- [ ] **Step 3: Implement the two modes**

Make manual entry the default. AI mode provides one text area, concise privacy guidance, progress/error state, and a “生成计划草稿” button. It must not display the manual form while analyzing. After a run is ready, render the shared review component. Preserve the compact collaborator control in manual mode.

- [ ] **Step 4: Run full verification**

Run:

```powershell
pytest bowei_ai_dashboard/tests/test_project_meeting_review.py bowei_ai_dashboard/tests/test_task_plan_proposals.py -q
npm run test:unit
node --test tests/keyTaskExecutionWorkspace.test.mjs
npm run build
git diff --check origin/main..HEAD
```

Expected: project tests and the focused/new frontend tests PASS; any unrelated pre-existing main-branch failure must be reported separately with its source evidence.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.tsx frontend/src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx frontend/tests/keyTaskExecutionWorkspace.test.mjs frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx
git commit -m "feat: add AI text planning to key task workspace"
```
